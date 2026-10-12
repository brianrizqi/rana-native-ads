# Results summary

| run | n | acc [95% CI] | macro-F1 [95% CI] | MCC | invalid |
|---|---|---|---|---|---|
| gemma3-12b__reasoning_first/test__rag_k5 | 2165 | 0.9709 [0.9629, 0.9772] | 0.9709 [0.9640, 0.9778] | 0.9420 | 0 |
| gemma3-12b__reasoning_first/test__norag | 2165 | 0.9686 [0.9604, 0.9751] | 0.9686 [0.9611, 0.9760] | 0.9373 | 0 |
| encoders__xlm-roberta-base/test | 2165 | 0.9626 [0.9537, 0.9698] | 0.9626 [0.9543, 0.9704] | 0.9252 | 0 |
| encoders__bert-base-multilingual-cased/test | 2165 | 0.9547 [0.9451, 0.9627] | 0.9547 [0.9458, 0.9630] | 0.9095 | 0 |
| encoders__indobert-base-p1/test | 2165 | 0.9483 [0.9381, 0.9568] | 0.9483 [0.9390, 0.9570] | 0.8966 | 0 |
| knn/e5-large/test__weighted_k5 | 2165 | 0.9053 [0.8923, 0.9169] | 0.9052 [0.8932, 0.9173] | 0.8133 | 0 |
| knn/e5-large/test__1nn | 2165 | 0.9002 [0.8869, 0.9122] | 0.9001 [0.8864, 0.9127] | 0.8020 | 0 |
| encoders__senada/test | 2165 | 0.8998 [0.8864, 0.9117] | 0.8998 [0.8868, 0.9113] | 0.7996 | 0 |
| knn/bge-m3/test__weighted_k5 | 2165 | 0.8938 [0.8801, 0.9061] | 0.8937 [0.8813, 0.9067] | 0.7893 | 0 |
| knn/bge-m3/test__1nn | 2165 | 0.8818 [0.8675, 0.8947] | 0.8817 [0.8679, 0.8951] | 0.7638 | 0 |
| encoders__bert-base-multilingual-cased/test_xsource | 2367 | 0.8724 [0.8584, 0.8853] | 0.8717 [0.8576, 0.8849] | 0.7585 | 0 |
| encoders__indobert-base-p1/test_xsource | 2367 | 0.8640 [0.8496, 0.8772] | 0.8630 [0.8484, 0.8763] | 0.7447 | 0 |
| knn/bge-m3/test_xsource__weighted_k5 | 2367 | 0.8509 [0.8359, 0.8646] | 0.8506 [0.8356, 0.8652] | 0.7020 | 0 |
| knn/e5-large/test_xsource__weighted_k5 | 2367 | 0.8369 [0.8215, 0.8513] | 0.8365 [0.8220, 0.8519] | 0.6749 | 0 |
| knn/minilm/test__weighted_k5 | 2165 | 0.8309 [0.8146, 0.8461] | 0.8302 [0.8146, 0.8461] | 0.6684 | 0 |
| knn/minilm/test__1nn | 2165 | 0.8083 [0.7912, 0.8243] | 0.8080 [0.7911, 0.8246] | 0.6192 | 0 |
| knn/e5-large/test_xsource__1nn | 2367 | 0.8010 [0.7844, 0.8166] | 0.8009 [0.7843, 0.8173] | 0.6019 | 0 |
| knn/bge-m3/test_xsource__1nn | 2367 | 0.7976 [0.7810, 0.8133] | 0.7975 [0.7807, 0.8137] | 0.5951 | 0 |
| gemma3-12b__reasoning_first/test_xsource__rag_k5 | 2367 | 0.7921 [0.7753, 0.8080] | 0.7917 [0.7741, 0.8072] | 0.5901 | 0 |
| gemma3-12b__reasoning_first/test_xsource__norag | 2367 | 0.7858 [0.7688, 0.8019] | 0.7858 [0.7697, 0.8021] | 0.5728 | 0 |
| encoders__senada/test_xsource | 2367 | 0.7900 [0.7732, 0.8060] | 0.7849 [0.7675, 0.8004] | 0.6203 | 0 |
| zeroshot__gemma3-12b/test__norag | 2165 | 0.7487 [0.7300, 0.7665] | 0.7487 [0.7302, 0.7663] | 0.4976 | 0 |
| knn/minilm/test_xsource__weighted_k5 | 2367 | 0.7220 [0.7036, 0.7397] | 0.7214 [0.7029, 0.7396] | 0.4440 | 0 |
| knn/minilm/test_xsource__1nn | 2367 | 0.6751 [0.6560, 0.6937] | 0.6746 [0.6556, 0.6933] | 0.3498 | 0 |
| encoders__xlm-roberta-base/test_xsource | 2367 | 0.6646 [0.6453, 0.6833] | 0.6612 [0.6416, 0.6799] | 0.3314 | 0 |

| A | B | b | c | diff [95% CI] | p exact | p Holm |
|---|---|---|---|---|---|---|
| knn/bge-m3/test__weighted_k5 | gemma3-12b__reasoning_first/test__rag_k5 | 20 | 187 | +0.0771 [+0.0637, +0.0901] | 3.61e-35 | 1.81e-34 |
| encoders__xlm-roberta-base/test | gemma3-12b__reasoning_first/test__rag_k5 | 28 | 46 | +0.0083 [+0.0009, +0.0166] | 0.0474 | 0.0948 |
| encoders__indobert-base-p1/test | gemma3-12b__reasoning_first/test__rag_k5 | 23 | 72 | +0.0226 [+0.0139, +0.0314] | 4.76e-07 | 1.43e-06 |
| encoders__senada/test | gemma3-12b__reasoning_first/test__rag_k5 | 23 | 177 | +0.0711 [+0.0591, +0.0836] | 1.24e-30 | 4.97e-30 |
| encoders__senada/test_xsource | gemma3-12b__reasoning_first/test_xsource__rag_k5 | 274 | 279 | +0.0021 [-0.0177, +0.0215] | 0.865 | 0.865 |
