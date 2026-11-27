"""
Instruction sheet ("petunjuk") added as the first tab of every human-study workbook, so annotators and raters
see the definitions, the meaning of each column and a filled example without opening the separate guide.
Data are always read from the named data sheet (anotasi / penilaian / validasi_edit), never from whichever tab
was active when the file was saved.
"""

SIGNALS_ID = [
    ("Positive tone (ya / netral / tidak)",
     "Artikel berbicara menguntungkan tentang hal yang diberitakan: memuji, menonjolkan prestasi, penghargaan, "
     "keunggulan. Netral: melaporkan tanpa condong memuji atau mengkritik. Tidak: nada kritis atau negatif."),
    ("Persuasive language (ya / tidak)",
     "Bahasa dipilih untuk meyakinkan pembaca, bukan sekadar memberi informasi: superlatif, ajakan bertindak, "
     "janji kepada pembaca, penekanan manfaat. Kalimat fakta, angka, atau jadwal tidak termasuk."),
    ("Brand promotion (ya / tidak)",
     "Produk, layanan, atau organisasi tertentu dipromosikan secara eksplisit dengan namanya. "
     "Menyebut nama saja belum cukup."),
    ("Single perspective (ya / tidak)",
     "Artikel hanya menyajikan satu sudut pandang, biasanya pihak yang diberitakan, tanpa pandangan pembanding, "
     "kritik, atau alternatif. Yang dinilai: apakah artikel mengadopsi sudut pandang pihak itu."),
]
LABEL_RULE = ("Label adalah penilaian atas artikel secara utuh: apakah artikel ditulis untuk mempromosikan sesuatu? "
              "Ulasan produk, opini, dan berita korporat yang memuat kritik atau lebih dari satu sudut pandang tetap "
              "berita murni / Pure News, walaupun nadanya positif dan menyebut merek.")
EXAMPLE_TEXT = ("[1] Gubernur Provinsi X menerima tiga penghargaan nasional atas program infrastruktur tahun ini. "
                "[2] \"Ini bukti komitmen kami untuk memastikan setiap warga merasakan pembangunan,\" ujarnya. "
                "[3] Ia berjanji memperbaiki jalan dan sekolah di seluruh kabupaten pada tahun depan. "
                "[4] Menurutnya, Provinsi X kini menjadi contoh daerah yang progresif.  (CONTOH FIKTIF)")
RULES = ["Kerjakan sendiri; jangan berdiskusi dengan peserta lain sampai file dikembalikan.",
         "Jangan mencari artikel di internet. Nama media dan URL sengaja disembunyikan.",
         "Jangan mengganti nama file, menambah atau menghapus sheet, atau menambah, menghapus, mengurutkan ulang baris.",
         "Isi lewat pilihan dropdown atau angka yang diminta. Simpan sebagai .xlsx (dari Google Sheets: unduh sebagai .xlsx).",
         "Simpan berkala. Kirim kembali file ini setelah semua baris terisi."]

GUIDES = {
    "anotasi": {
        "title": "PETUNJUK ANOTASI: sinyal framing promosi pada artikel berita",
        "intro": ["Isi lembar 'anotasi'. Satu baris = satu artikel. Kalimat artikel diberi nomor [1], [2], ... ",
                  "Langkah: baca seluruh artikel, nilai empat sinyal satu per satu, tulis nomor kalimat bukti untuk "
                  "sinyal yang 'ya', baru beri label, lalu isi keyakinan.",
                  "Nilai hanya teks yang tampil; artikel panjang dipotong. Tidak ada jawaban yang diharapkan."],
        "columns": [("positive_tone", "ya / netral / tidak"), ("persuasive", "ya / tidak"),
                    ("brand_promotion", "ya / tidak"), ("single_perspective", "ya / tidak"),
                    ("label", "native ads / berita murni"),
                    ("evidence_...", "Nomor kalimat bukti, dipisah koma, mis. 2, 5. Isi hanya bila sinyal itu 'ya'. Opsional."),
                    ("confidence", "Keyakinan atas label: 1 sangat ragu, 3 cukup yakin, 5 sangat yakin"),
                    ("comment", "Opsional: alasan bila ragu, atau teks bermasalah")],
        "example": [("positive_tone", "ya"), ("persuasive", "ya"), ("brand_promotion", "ya"),
                    ("single_perspective", "ya"), ("label", "native ads"), ("evidence_positive_tone", "1, 4"),
                    ("evidence_persuasive", "2"), ("evidence_brand_promotion", "1, 4"),
                    ("evidence_single_perspective", "2, 3"), ("confidence", "5")],
    },
    "studi_r": {
        "title": "PETUNJUK STUDI R: apakah contoh artikel serupa membantu keputusan?",
        "intro": ["Isi lembar 'penilaian'. Satu baris = satu artikel, dengan keluaran sistem (empat sinyal dan label).",
                  "Pada sebagian artikel, kolom retrieved_examples berisi lima contoh artikel serupa beserta labelnya; "
                  "pada artikel lain tertulis '(not shown for this article)'. Ini disengaja: nilai seperti biasa.",
                  "Keluaran sistem bisa salah. Baca artikelnya sendiri; jangan hanya mengikuti label sistem atau contoh."],
        "columns": [("your_decision_native (1/0)", "Keputusan Anda sendiri: 1 = Native Ads, 0 = Pure News"),
                    ("accept_model_label (1/0)", "1 = Anda menerima label sistem, 0 = tidak"),
                    ("confidence (1-5)", "Keyakinan atas keputusan Anda: 1 sangat ragu, 5 sangat yakin"),
                    ("minutes", "Opsional: perkiraan menit untuk artikel ini"),
                    ("comment", "Opsional: alasan, terutama bila tidak setuju dengan sistem")],
        "example": [("your_decision_native (1/0)", "1"), ("accept_model_label (1/0)", "1"),
                    ("confidence (1-5)", "5"), ("minutes", "3")],
    },
    "studi_m": {
        "title": "PETUNJUK STUDI M: keluaran mana yang lebih berguna?",
        "intro": ["Isi lembar 'penilaian'. Setiap artikel muncul sekali, diikuti empat keluaran sistem A, B, C, D "
                  "(baris berikutnya bertuliskan '(same article as above)').",
                  "Urutan A sampai D diacak per artikel. Nilai setiap keluaran secara terpisah.",
                  "Kolom retrieved_examples menampilkan contoh artikel serupa yang dilihat keluaran itu, sebagai konteks."],
        "columns": [("label_ok", "1 = setuju dengan label keluaran ini, 0 = tidak"),
                    ("positive_tone_ok ... single_perspective_ok", "1 = setuju dengan penilaian sinyal itu, 0 = tidak"),
                    ("editorial_usefulness", "1 tidak membantu atau menyesatkan; 2 sedikit membantu; 3 cukup, perlu "
                                             "diperiksa ulang; 4 membantu, sedikit koreksi; 5 bisa langsung dipakai"),
                    ("comment", "Opsional")],
        "example": [("label_ok", "1"), ("positive_tone_ok", "1"), ("persuasive_ok", "1"), ("brand_promotion_ok", "1"),
                    ("single_perspective_ok", "1"), ("editorial_usefulness", "5")],
    },
    "validasi_edit": {
        "title": "PETUNJUK VALIDASI EDIT: apakah edit hanya mengubah satu hal yang diminta?",
        "intro": ["Isi lembar 'validasi_edit'. Setiap baris berisi perintah edit, teks asli, dan teks hasil edit.",
                  "Setiap edit diminta menghilangkan tepat satu sinyal dan mempertahankan fakta, panjang, dan tiga "
                  "sinyal lain. Edit parafrase adalah kontrol: tidak boleh ada sinyal yang hilang.",
                  "Edit brand promotion memang mengganti nama merek dengan sebutan umum; edit single perspective memang "
                  "menambah satu pandangan pihak lain. Keduanya bukan pelanggaran facts_preserved."],
        "columns": [("target_removed (1/0)", "1 = sinyal yang diminta hilang (parafrase: tidak ada yang hilang), 0 = masih ada"),
                    ("other_signals_unchanged (1/0)", "1 = tiga sinyal lain tetap ada, 0 = ada yang ikut hilang atau berubah"),
                    ("facts_preserved (1/0)", "1 = nama, angka, tanggal, peristiwa tetap, 0 = ada yang berubah di luar perintah"),
                    ("comment", "Tulis singkat apa yang salah bila ada nilai 0")],
        "example": [("target_removed (1/0)", "1"), ("other_signals_unchanged (1/0)", "1"), ("facts_preserved (1/0)", "1")],
    },
}


def add_guide(wb, kind):
    """Insert the 'petunjuk' tab first and open the workbook on it."""
    from openpyxl.styles import Alignment, Font, PatternFill
    g = GUIDES[kind]
    ws = wb.create_sheet("petunjuk", 0)
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 110
    bold, head = Font(bold=True), Font(bold=True, size=13)
    band = PatternFill("solid", fgColor="DDEBF7")
    def put(a="", b="", font=None, fill=None):
        ws.append([a, b])
        r = ws.max_row
        for c in ws[r]:
            c.alignment = Alignment(wrap_text=True, vertical="top")
            if font:
                c.font = font
            if fill:
                c.fill = fill
    put(g["title"], font=head)
    for line in g["intro"]:
        put("", line)
    put()
    put("ATURAN", font=bold, fill=band)
    for i, line in enumerate(RULES, 1):
        put(f"{i}.", line)
    put()
    put("EMPAT SINYAL", font=bold, fill=band)
    for name, desc in SIGNALS_ID:
        put(name, desc)
    put("Label", LABEL_RULE)
    put()
    put("KOLOM YANG DIISI (kuning)", font=bold, fill=band)
    for name, desc in g["columns"]:
        put(name, desc)
    put()
    put("CONTOH PENGISIAN", font=bold, fill=band)
    put("Teks contoh", EXAMPLE_TEXT)
    for name, val in g["example"]:
        put(name, val)
    wb.active = 0
    return ws


def data_rows(path, sheet):
    """All rows of the named data sheet, falling back to the first non-guide sheet for older files."""
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True)
    if sheet in wb.sheetnames:
        ws = wb[sheet]
    else:
        ws = next(wb[n] for n in wb.sheetnames if n != "petunjuk")
    return list(ws.iter_rows(values_only=True))
