# Results summary

| run | n | acc [95% CI] | macro-F1 [95% CI] | MCC | invalid |
|---|---|---|---|---|---|
| gemma3-12b__reasoning_first/test__rag_k5 | 2165 | 0.9709 [0.9629, 0.9772] | 0.9709 [0.9635, 0.9778] | 0.9420 | 0 |
| gemma3-12b__label_first/test__rag_k5 | 2165 | 0.9695 [0.9614, 0.9760] | 0.9695 [0.9626, 0.9764] | 0.9390 | 0 |
| gemma3-12b__label_first/test__norag | 2165 | 0.9686 [0.9604, 0.9751] | 0.9686 [0.9607, 0.9755] | 0.9372 | 0 |
| gemma3-12b__reasoning_first/test__norag | 2165 | 0.9686 [0.9604, 0.9751] | 0.9686 [0.9612, 0.9760] | 0.9373 | 0 |
| qwen3.5-9b__reasoning_first/test__rag_k5 | 2165 | 0.9681 [0.9599, 0.9747] | 0.9681 [0.9607, 0.9755] | 0.9364 | 0 |
| gemma2-9b__reasoning_first/test__rag_k5 | 2165 | 0.9663 [0.9578, 0.9731] | 0.9663 [0.9584, 0.9736] | 0.9327 | 0 |
| gemma3-12b__reasoning_first_s42/test__rag_k5 | 2165 | 0.9658 [0.9573, 0.9727] | 0.9658 [0.9580, 0.9737] | 0.9322 | 0 |
| qwen3-8b__reasoning_first/test__rag_k5 | 2165 | 0.9649 [0.9563, 0.9719] | 0.9649 [0.9566, 0.9723] | 0.9301 | 0 |
| gemma3-12b__reasoning_first_s42/test__norag | 2165 | 0.9640 [0.9553, 0.9710] | 0.9640 [0.9561, 0.9718] | 0.9283 | 0 |
| qwen3.5-9b__reasoning_first/test__norag | 2165 | 0.9630 [0.9542, 0.9702] | 0.9630 [0.9547, 0.9704] | 0.9268 | 0 |
| qwen2.5-14b__reasoning_first/test__rag_k5 | 2165 | 0.9626 [0.9537, 0.9698] | 0.9626 [0.9538, 0.9704] | 0.9259 | 0 |
| gemma3-12b__reasoning_first_s2024/test__norag | 2165 | 0.9617 [0.9527, 0.9690] | 0.9617 [0.9538, 0.9691] | 0.9233 | 0 |
| gemma2-9b__reasoning_first/test__norag | 2165 | 0.9617 [0.9527, 0.9690] | 0.9617 [0.9538, 0.9695] | 0.9234 | 0 |
| gemma3-12b__reasoning_first_s2024/test__rag_k5 | 2165 | 0.9612 [0.9522, 0.9686] | 0.9612 [0.9533, 0.9686] | 0.9224 | 0 |
| qwen3.5-2b__reasoning_first/test__rag_k5 | 2165 | 0.9612 [0.9522, 0.9686] | 0.9612 [0.9533, 0.9690] | 0.9228 | 0 |
| gemma3-4b__label_first/test__rag_k5 | 2165 | 0.9607 [0.9517, 0.9681] | 0.9607 [0.9524, 0.9686] | 0.9215 | 0 |
| qwen3-8b__reasoning_first/test__norag | 2165 | 0.9594 [0.9502, 0.9669] | 0.9594 [0.9510, 0.9676] | 0.9188 | 0 |
| gemma3-4b__label_only/test__rag_k5 | 2165 | 0.9594 [0.9502, 0.9669] | 0.9594 [0.9506, 0.9681] | 0.9188 | 0 |
| gemma3-4b__reasoning_first/test__rag_k5 | 2165 | 0.9589 [0.9497, 0.9665] | 0.9589 [0.9501, 0.9667] | 0.9180 | 0 |
| gemma3-12b__label_only/test__rag_k5 | 2165 | 0.9566 [0.9472, 0.9644] | 0.9566 [0.9482, 0.9653] | 0.9133 | 0 |
| qwen2.5-14b__reasoning_first/test__norag | 2165 | 0.9566 [0.9472, 0.9644] | 0.9566 [0.9473, 0.9649] | 0.9136 | 0 |
| gemma3-4b__label_only/test__norag | 2165 | 0.9557 [0.9462, 0.9636] | 0.9557 [0.9464, 0.9639] | 0.9115 | 0 |
| gemma3-4b__label_first/test__norag | 2165 | 0.9547 [0.9451, 0.9627] | 0.9547 [0.9455, 0.9630] | 0.9099 | 0 |
| gemma3-4b__reasoning_first/test__norag | 2165 | 0.9520 [0.9421, 0.9602] | 0.9520 [0.9427, 0.9603] | 0.9039 | 0 |
| llama3.2-1b__reasoning_first/test__rag_k5 | 2165 | 0.9515 [0.9416, 0.9598] | 0.9515 [0.9427, 0.9603] | 0.9030 | 0 |
| gemma3-12b__assessment_only/test__norag | 2165 | 0.9487 [0.9386, 0.9573] | 0.9487 [0.9390, 0.9575] | 0.8975 | 0 |
| gemma3-4b__assessment_only/test__rag_k5 | 2165 | 0.9478 [0.9376, 0.9564] | 0.9478 [0.9384, 0.9570] | 0.8956 | 0 |
| gemma3-12b__label_only/test__norag | 2165 | 0.9473 [0.9371, 0.9560] | 0.9473 [0.9376, 0.9561] | 0.8954 | 0 |
| llama3.2-1b__reasoning_first/test__norag | 2165 | 0.9469 [0.9366, 0.9556] | 0.9469 [0.9371, 0.9561] | 0.8939 | 0 |
| qwen3.5-2b__reasoning_first/test__norag | 2165 | 0.9436 [0.9331, 0.9526] | 0.9436 [0.9339, 0.9529] | 0.8874 | 0 |
| gemma3-1b__reasoning_first/test__rag_k5 | 2165 | 0.9436 [0.9331, 0.9526] | 0.9436 [0.9330, 0.9524] | 0.8877 | 0 |
| deepseek-r1-llama-8b__reasoning_first/test__rag_k5 | 2165 | 0.9413 [0.9306, 0.9505] | 0.9413 [0.9306, 0.9510] | 0.8828 | 0 |
| gemma3-4b__assessment_only/test__norag | 2165 | 0.9413 [0.9306, 0.9505] | 0.9413 [0.9316, 0.9510] | 0.8828 | 0 |
| gemma3-270m__reasoning_first/test__norag | 2165 | 0.9349 [0.9237, 0.9445] | 0.9349 [0.9246, 0.9455] | 0.8702 | 15 |
| deepseek-r1-llama-8b__reasoning_first/test__norag | 2165 | 0.9335 [0.9222, 0.9432] | 0.9335 [0.9224, 0.9436] | 0.8672 | 0 |
| gemma3-1b__reasoning_first/test__norag | 2165 | 0.9321 [0.9207, 0.9420] | 0.9320 [0.9213, 0.9427] | 0.8662 | 0 |
| gemma3-270m__reasoning_first/test__rag_k5 | 2165 | 0.9316 [0.9202, 0.9415] | 0.9316 [0.9213, 0.9426] | 0.8642 | 20 |
| gemma3-12b__assessment_only/test__rag_k5 | 2165 | 0.9284 [0.9168, 0.9385] | 0.9284 [0.9172, 0.9390] | 0.8572 | 0 |
| zeroshot__gemma3-12b/test__norag | 2165 | 0.7487 [0.7300, 0.7665] | 0.7487 [0.7312, 0.7668] | 0.4976 | 0 |

| A | B | b | c | diff [95% CI] | p exact | p Holm |
|---|---|---|---|---|---|---|
| gemma3-4b__label_only/test__norag | gemma3-4b__reasoning_first/test__norag | 47 | 39 | -0.0037 [-0.0120, +0.0046] | 0.451 | 1 |
| gemma3-4b__label_only/test__rag_k5 | gemma3-4b__reasoning_first/test__rag_k5 | 36 | 35 | -0.0005 [-0.0083, +0.0074] | 1 | 1 |
| gemma3-4b__label_first/test__norag | gemma3-4b__reasoning_first/test__norag | 42 | 36 | -0.0028 [-0.0111, +0.0051] | 0.572 | 1 |
| gemma3-4b__label_first/test__rag_k5 | gemma3-4b__reasoning_first/test__rag_k5 | 33 | 29 | -0.0018 [-0.0088, +0.0055] | 0.704 | 1 |
| gemma3-4b__assessment_only/test__norag | gemma3-4b__reasoning_first/test__norag | 19 | 42 | +0.0106 [+0.0037, +0.0180] | 0.00444 | 0.0311 |
| gemma3-4b__assessment_only/test__rag_k5 | gemma3-4b__reasoning_first/test__rag_k5 | 16 | 40 | +0.0111 [+0.0046, +0.0180] | 0.00184 | 0.0147 |
| gemma3-12b__label_only/test__norag | gemma3-12b__reasoning_first/test__norag | 14 | 60 | +0.0212 [+0.0134, +0.0286] | 6.22e-08 | 6.84e-07 |
| gemma3-12b__label_only/test__rag_k5 | gemma3-12b__reasoning_first/test__rag_k5 | 11 | 42 | +0.0143 [+0.0083, +0.0212] | 2.25e-05 | 0.000202 |
| gemma3-12b__label_first/test__norag | gemma3-12b__reasoning_first/test__norag | 20 | 20 | +0.0000 [-0.0060, +0.0060] | 1 | 1 |
| gemma3-12b__label_first/test__rag_k5 | gemma3-12b__reasoning_first/test__rag_k5 | 16 | 19 | +0.0014 [-0.0037, +0.0065] | 0.736 | 1 |
| gemma3-12b__assessment_only/test__norag | gemma3-12b__reasoning_first/test__norag | 16 | 59 | +0.0199 [+0.0125, +0.0273] | 6.11e-07 | 6.11e-06 |
| gemma3-12b__assessment_only/test__rag_k5 | gemma3-12b__reasoning_first/test__rag_k5 | 11 | 103 | +0.0425 [+0.0333, +0.0522] | 6.92e-20 | 8.3e-19 |
