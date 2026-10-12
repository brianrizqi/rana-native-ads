"""SENADA retrained on the frozen partition (R1-C9, R2-5).

A PyTorch port of the authors' original Keras notebook (Concatenate.ipynb), keeping its
architecture and hyperparameters and replacing only the data handling:

  features   last four hidden layers of a BERT-base encoder concatenated, 48 tokens x 3072
             (the original input shape; the original extraction script was not preserved, so
             the encoder is a documented assumption, IndoBERT-base by default)
  base       one model per signal, trained on half A of the training partition:
               positive tone       Conv1D(512, 3, tanh) -> GlobalMaxPool -> Dropout(0.1) -> Dense(3)
               persuasive          BiGRU(256, seq) -> BiGRU(256) -> Dropout(0.1) -> Dense(2)
               brand promotion     BiLSTM(256, seq) -> BiLSTM(256) -> Dropout(0.1) -> Dense(2)
               single perspective  BiLSTM(256, seq) -> BiLSTM(256) -> Flatten -> Dropout(0.5) -> Dense(2)
             RMSprop (Keras defaults), 30 epochs, batch 128, final weights kept
  meta       the 512-d penultimate output of each base model ("streaming vector sentence"),
             concatenated and trained on half B: BiLSTM(64, seq) -> BiLSTM(64) -> Dropout(0.3)
             -> attention Dense(128, softmax, L2 0.5) concatenated -> Dense(2, ReLU);
             Adam 5e-4 with decay 1e-6, ReduceLROnPlateau(0.7, patience 3) on validation loss,
             50 epochs, batch 128
  losses     binary cross-entropy on one-hot targets, as in the notebook

The original notebook trained base and meta models on two halves of a label-sorted sheet and
evaluated on a K-fold split of the second half; here half A / half B are a stratified random
split of the training partition, the validation partition only monitors loss, and evaluation
uses the locked test partition and the withheld publisher.

    python revision/senada_baseline.py --split-dir revision/splits/main --out-dir revision/results/encoders__senada
"""

import argparse
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SIGNALS, env_versions, read_jsonl, write_json, write_jsonl

SIGNAL_CLASSES = {"positive_tone": ["ya", "tidak", "netral"], "persuasive": ["ya", "tidak"],
                  "brand_promotion": ["ya", "tidak"], "single_perspective": ["ya", "tidak"]}
LABEL_CLASSES = ["native ads", "berita murni"]          # notebook order: native ads = 0
SPLITS = ("train", "val", "test", "test_xsource")


def set_seed(seed):
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def embed(rows, encoder, max_len, cache, device, batch=32):
    """Concatenation of the last four hidden layers, max_len tokens x (4 * hidden), float16 on disk."""
    if cache.exists():
        arr = np.load(cache, mmap_mode="r")
        if arr.shape[0] == len(rows):
            return arr
    import torch
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(encoder)
    model = AutoModel.from_pretrained(encoder, output_hidden_states=True).to(device).eval()
    out = np.lib.format.open_memmap(cache, mode="w+", dtype=np.float16,
                                    shape=(len(rows), max_len, 4 * model.config.hidden_size))
    with torch.no_grad():
        for i in range(0, len(rows), batch):
            enc = tok([r["text"] for r in rows[i:i + batch]], max_length=max_len, truncation=True,
                      padding="max_length", return_tensors="pt").to(device)
            hs = model(**enc).hidden_states
            out[i:i + batch] = torch.cat(hs[-4:], dim=-1).float().cpu().numpy().astype(np.float16)
    out.flush()
    return np.load(cache, mmap_mode="r")


def build_models(dim):
    import torch
    from torch import nn

    class BiRNN(nn.Module):
        def __init__(self, cell, n_out, flatten_dropout=None):
            super().__init__()
            rnn = nn.GRU if cell == "gru" else nn.LSTM
            self.r1 = rnn(dim, 256, batch_first=True, bidirectional=True)
            self.r2 = rnn(512, 256, batch_first=True, bidirectional=True)
            self.drop = nn.Dropout(flatten_dropout or 0.1)
            self.out = nn.Linear(512, n_out)

        def features(self, x):
            h, _ = self.r1(x)
            _, hn = self.r2(h)
            hn = hn[0] if isinstance(hn, tuple) else hn
            return torch.cat([hn[-2], hn[-1]], dim=-1)           # last forward + last backward state

        def forward(self, x):
            return self.out(self.drop(self.features(x)))

    class CNN(nn.Module):
        def __init__(self, n_out):
            super().__init__()
            self.conv = nn.Conv1d(dim, 512, kernel_size=3)
            self.drop = nn.Dropout(0.1)
            self.out = nn.Linear(512, n_out)

        def features(self, x):
            return torch.tanh(self.conv(x.transpose(1, 2))).amax(dim=-1)

        def forward(self, x):
            return self.out(self.drop(self.features(x)))

    return {"positive_tone": (lambda: CNN(3), "softmax"),
            "persuasive": (lambda: BiRNN("gru", 2), "sigmoid"),
            "brand_promotion": (lambda: BiRNN("lstm", 2), "sigmoid"),
            "single_perspective": (lambda: BiRNN("lstm", 2, flatten_dropout=0.5), "sigmoid")}


def keras_bce(logits, onehot, activation):
    """binary_crossentropy on probabilities, clipped as Keras does."""
    import torch
    p = {"sigmoid": torch.sigmoid, "softmax": lambda z: torch.softmax(z, -1), "relu": torch.relu}[activation](logits)
    p = p.clamp(1e-7, 1 - 1e-7)
    return -(onehot * p.log() + (1 - onehot) * (1 - p).log()).mean()


def batches(n, size, shuffle, rng):
    idx = rng.permutation(n) if shuffle else np.arange(n)
    for i in range(0, n, size):
        yield idx[i:i + size]


def train_base(make, activation, X, y, Xv, yv, n_cls, device, epochs, seed, log):
    import torch
    set_seed(seed)
    model = make().to(device)
    opt = torch.optim.RMSprop(model.parameters(), lr=1e-3, alpha=0.9, eps=1e-7)
    eye = torch.eye(n_cls, device=device)
    rng = np.random.default_rng(seed)
    for ep in range(epochs):
        model.train()
        for b in batches(len(X), 128, True, rng):
            xb = torch.tensor(np.asarray(X[np.sort(b)]), dtype=torch.float32, device=device)
            yb = eye[torch.tensor(y[np.sort(b)], device=device)]
            opt.zero_grad()
            keras_bce(model(xb), yb, activation).backward()
            opt.step()
        vl = evaluate_loss(model, Xv, yv, eye, activation, device)
        log(f"    epoch {ep + 1}/{epochs} val_loss {vl:.4f}")
    return model.eval()


def evaluate_loss(model, X, y, eye, activation, device):
    import torch
    model.eval()
    tot, n = 0.0, 0
    with torch.no_grad():
        for b in batches(len(X), 256, False, None):
            xb = torch.tensor(np.asarray(X[b]), dtype=torch.float32, device=device)
            tot += keras_bce(model(xb), eye[torch.tensor(y[b], device=device)], activation).item() * len(b)
            n += len(b)
    return tot / max(n, 1)


def predict(model, X, device, feats=False):
    import torch
    outs = []
    with torch.no_grad():
        for b in batches(len(X), 256, False, None):
            xb = torch.tensor(np.asarray(X[b]), dtype=torch.float32, device=device)
            outs.append((model.features(xb) if feats else model(xb)).float().cpu().numpy())
    return np.concatenate(outs)


def train_meta(V, y, Vv, yv, device, seed, log, epochs=50):
    import torch
    from torch import nn
    set_seed(seed)

    class Meta(nn.Module):
        def __init__(self, d):
            super().__init__()
            self.l1 = nn.LSTM(d, 64, batch_first=True, bidirectional=True)
            self.l2 = nn.LSTM(128, 64, batch_first=True, bidirectional=True)
            self.drop = nn.Dropout(0.3)
            self.att = nn.Linear(128, 128)
            self.out = nn.Linear(256, 2)

        def forward(self, v):
            h, _ = self.l1(v.unsqueeze(1))                         # expand_dims: sequence of length 1
            _, (hn, _) = self.l2(h)
            x = self.drop(torch.cat([hn[-2], hn[-1]], dim=-1))
            a = torch.softmax(self.att(x), dim=-1)
            return self.out(torch.cat([x, a], dim=-1))             # ReLU applied in the loss, as Dense(2, relu)

    model = Meta(V.shape[1]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=5e-4, eps=1e-7)
    base_lr, it, best, wait = 5e-4, 0, float("inf"), 0     # Keras legacy decay + ReduceLROnPlateau
    eye = torch.eye(2, device=device)
    rng = np.random.default_rng(seed)
    Vt, yt = torch.tensor(V, device=device), torch.tensor(y, device=device)
    for ep in range(epochs):
        model.train()
        for b in batches(len(V), 128, True, rng):
            b = torch.tensor(b, device=device)
            for g in opt.param_groups:
                g["lr"] = base_lr / (1.0 + 1e-6 * it)
            opt.zero_grad()
            loss = keras_bce(model(Vt[b]), eye[yt[b]], "relu") + 0.5 * model.att.weight.pow(2).sum()
            loss.backward()
            opt.step()
            it += 1
        model.eval()
        with torch.no_grad():
            vl = keras_bce(model(torch.tensor(Vv, device=device)), eye[torch.tensor(yv, device=device)], "relu").item()
        if vl < best - 1e-4:
            best, wait = vl, 0
        else:
            wait += 1
            if wait >= 3:
                base_lr, wait = max(base_lr * 0.7, 1e-6), 0
        log(f"    meta epoch {ep + 1}/{epochs} val_loss {vl:.4f}")
    return model.eval()


def main():
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-dir", default="revision/splits/main")
    ap.add_argument("--out-dir", default="revision/results/encoders__senada")
    ap.add_argument("--encoder", default="indobenchmark/indobert-base-p1")
    ap.add_argument("--max-len", type=int, default=48)
    ap.add_argument("--cache-dir", default="revision/cache/senada")
    ap.add_argument("--base-epochs", type=int, default=30)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-train", type=int, default=None, help="Debug only")
    a = ap.parse_args()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    out, cache = Path(a.out_dir), Path(a.cache_dir)
    out.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    log = lambda m: print(m, flush=True)
    t0 = time.time()

    data = {}
    for sp in SPLITS:
        f = Path(a.split_dir) / f"{sp}.jsonl"
        if f.exists():
            rows = read_jsonl(f)
            if sp == "train" and a.max_train:
                rows = rows[:a.max_train]
            data[sp] = rows
    feats = {sp: embed(rows, a.encoder, a.max_len, cache / f"{sp}_{a.max_len}.npy", device)
             for sp, rows in data.items()}
    log(f"features ready in {time.time() - t0:.0f}s: " + ", ".join(f"{k} {v.shape}" for k, v in feats.items()))

    # Stratified half split of the training partition: half A trains base models, half B the meta model
    train = data["train"]
    rng = np.random.default_rng(a.seed)
    half_a, half_b = [], []
    for lab in LABEL_CLASSES:
        idx = [i for i, r in enumerate(train) if r["label"] == lab]
        rng.shuffle(idx)
        half_a += idx[: len(idx) // 2]
        half_b += idx[len(idx) // 2:]
    half_a, half_b = np.sort(half_a), np.sort(half_b)

    def sig_y(rows, s):
        return np.array([SIGNAL_CLASSES[s].index(r["signals"][s]) if r["signals"].get(s) in SIGNAL_CLASSES[s] else 0
                         for r in rows])

    def lab_y(rows):
        return np.array([LABEL_CLASSES.index(r["label"]) for r in rows])

    Xa, Xb = feats["train"][half_a], feats["train"][half_b]
    tr_a = [train[i] for i in half_a]
    tr_b = [train[i] for i in half_b]
    models, vectors, sig_pred = build_models(feats["train"].shape[-1]), {}, {}
    t_train = time.time()
    for s, (make, act) in models.items():
        log(f"base model: {s}")
        m = train_base(make, act, Xa, sig_y(tr_a, s), feats["val"], sig_y(data["val"], s),
                       len(SIGNAL_CLASSES[s]), device, a.base_epochs, a.seed, log)
        vectors[s] = {"train_b": predict(m, Xb, device, feats=True)}
        for sp in ("val", "test", "test_xsource"):
            if sp in feats:
                vectors[s][sp] = predict(m, feats[sp], device, feats=True)
                sig_pred.setdefault(sp, {})[s] = predict(m, feats[sp], device).argmax(-1)
        del m
        torch.cuda.empty_cache()

    cat = lambda key: np.concatenate([vectors[s][key] for s in SIGNALS], axis=1).astype(np.float32)
    log("meta model")
    meta = train_meta(cat("train_b"), lab_y(tr_b), cat("val"), lab_y(data["val"]), device, a.seed, log)
    train_seconds = time.time() - t_train

    for sp in ("test", "test_xsource"):
        if sp not in data:
            continue
        t1 = time.time()
        with torch.no_grad():
            z = torch.relu(meta(torch.tensor(cat(sp), device=device))).cpu().numpy()
        infer_seconds = time.time() - t1
        pred = z.argmax(-1)
        rows = data[sp]
        write_jsonl(out / f"{sp}.jsonl", (
            {"id": r["id"], "lang": r["lang"], "host": r.get("host"), "section": r.get("section"),
             "label_gold": r["label"], "signals_gold": r["signals"], "label_pred": LABEL_CLASSES[int(p)],
             "signals_pred": {s: SIGNAL_CLASSES[s][int(sig_pred[sp][s][i])] for s in SIGNALS},
             "parse_ok": True, "label_source": "classifier",
             "condition": {"model": "senada", "encoder": a.encoder, "method": "stacked_ensemble"}}
            for i, (r, p) in enumerate(zip(rows, pred))))
        acc = float(np.mean([LABEL_CLASSES[int(p)] == r["label"] for r, p in zip(rows, pred)]))
        log(f"{sp}: accuracy {acc:.4f} ({len(rows)} articles, inference {infer_seconds:.1f}s)")
    write_json(out / "run_config.json", {**vars(a), "device": device, "half_a": len(half_a), "half_b": len(half_b),
                                         "train_seconds": round(train_seconds, 1), "versions": env_versions()})
    log(f"✅ -> {out} ({time.time() - t0:.0f}s total)")


if __name__ == "__main__":
    main()
