import streamlit as st
import numpy as np
import itertools
import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
import random

# ----------------------------------------
# 🌟 ページ設定
# ----------------------------------------
st.set_page_config(page_title="Dot Blot 最適化ツール（高速条件付き版）", page_icon="🧪", layout="wide")

st.markdown("""
<h1 style='text-align:center; color:#2c3e50;'>🧪 Dot Blot 最適化ツール（高速条件付き版）</h1>
<p style='text-align:center; color:gray; font-size:18px;'>
条件Aを100基準に正規化し、元のSDより改善された組み合わせのみを抽出します<br>
サンプルの区別なし・丸め処理なし
</p>
<hr style='border:1px solid #eee;'>
""", unsafe_allow_html=True)

# ----------------------------------------
# 📥 入力エリア
# ----------------------------------------
st.sidebar.header("⚙️ 設定")
num_rows = st.sidebar.number_input("条件（行）の数", min_value=2, max_value=10, value=4)
num_cols = st.sidebar.number_input("サンプル数（列）の数", min_value=2, max_value=10, value=5)
subset_n = st.sidebar.slider("各条件の並べ替え数（高速化）", 1, 120, 20)
st.sidebar.markdown("---")
st.sidebar.info("各条件ごとにカンマ区切りでサンプル値を入力してください。")

data = {}
cols = st.columns(2)
for i in range(num_rows):
    key = chr(65 + i)
    with cols[i % 2]:
        values = st.text_input(f"🔹 {key}（条件{i+1}）の値", "1.0, 1.0, 1.0, 1.0, 1.0")
        try:
            data[key] = [float(v.strip()) for v in values.split(",")]
        except:
            st.warning(f"{key}の入力を確認してください。")

# ----------------------------------------
# 🚀 実行
# ----------------------------------------
if st.button("🚀 計算を実行する", use_container_width=True, type="primary"):

    def nonzero_list(row):
        return [v for v in row if v != 0.0]

    def normalize_columns(columns):
        """条件Aを基準に100正規化"""
        ref = np.array(columns[0])
        normalized = []
        for col in columns:
            norm = np.where(ref != 0, col / ref * 100, np.nan)
            normalized.append(tuple(norm))
        return normalized

    def calc_sum_sd_from_columns(columns, labels):
        norm_cols = normalize_columns(columns)
        rows = list(zip(*norm_cols))
        sds, means = [], []
        for r in rows:
            arr = np.array([x for x in r if not np.isnan(x)])
            means.append(float(np.mean(arr)))
            sds.append(float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0)
        return sum(sds), sds, means, norm_cols

    # ----------------------------------------
    # 📊 前処理
    # ----------------------------------------
    nonzero_data = {k: nonzero_list(v) for k, v in data.items()}
    counts = [len(v) for v in nonzero_data.values()]
    k = min(counts)
    labels = list(nonzero_data.keys())
    st.info(f"✅ 使用サンプル数 k = {k} / 各条件の非ゼロ数: {counts}")

    # 並べ替えを部分的に抽出（準網羅）
    row_perms_list = [
        random.sample(list(itertools.permutations(v, k)), min(subset_n, len(list(itertools.permutations(v, k)))))
        for v in nonzero_data.values()
    ]
    total_combinations = np.prod([len(p) for p in row_perms_list])
    st.write(f"理論上の全組み合わせ数: {int(total_combinations):,} 通り")

    # ----------------------------------------
    # 🧮 基準SD計算
    # ----------------------------------------
    baseline_sum_sd, baseline_sds, baseline_means, _ = calc_sum_sd_from_columns(
        [tuple(nonzero_data[k][:k]) for k in labels], labels
    )
    st.write(f"🔹 基準構成の Sum_SD = {baseline_sum_sd:.3f}")

    # ----------------------------------------
    # 🚀 探索開始
    # ----------------------------------------
    seen, results = {}, []
    progress = st.progress(0)
    checked = 0
    total = int(total_combinations)

    for perm_set in itertools.product(*row_perms_list):
        checked += 1
        if checked % 500 == 0:
            progress.progress(min(checked / total, 1.0))

        cols = [tuple(perm[i] for perm in perm_set) for i in range(k)]
        key = tuple(sorted(tuple(round(x, 5) for x in col) for col in cols))
        if key in seen:
            continue
        seen[key] = True

        sum_sd, sds, means, norm_cols = calc_sum_sd_from_columns(cols, labels)
        if sum_sd < baseline_sum_sd:  # ←改善されたものだけ保存
            results.append({
                "sum_sd": sum_sd, "sds": sds, "means": means,
                "columns": cols, "norm_cols": norm_cols
            })

    progress.empty()
    st.success(f"🎉 計算完了！ 重複除外後の実際の組み合わせ数: {len(results):,}")

    # ----------------------------------------
    # 🏆 結果表示
    # ----------------------------------------
    results.sort(key=lambda x: x["sum_sd"])
    topn = min(10, len(results))
    sample_labels = [f"Sample{i+1}" for i in range(k)]

    for i, r in enumerate(results[:topn]):
        with st.expander(f"🏅 Rank {i+1} — Sum_SD: {r['sum_sd']:.6f}"):
            st.write(f"**SDs:** {', '.join(f'{v:.3f}' for v in r['sds'])}")
            st.write(f"**Means:** {', '.join(f'{v:.3f}' for v in r['means'])}")

            df_raw = pd.DataFrame(r["columns"], columns=sample_labels, index=labels)
            df_norm = pd.DataFrame(r["norm_cols"], columns=sample_labels, index=labels)

            st.markdown("**Raw 値（行=条件 / 列=サンプル）**")
            st.dataframe(df_raw.style.format(precision=3), use_container_width=True)
            st.markdown("**Normalized（条件A=100基準）**")
            st.dataframe(df_norm.style.format(precision=3), use_container_width=True)

    # ----------------------------------------
    # 📈 Excel出力
    # ----------------------------------------
    wb = Workbook()
    ws = wb.active
    ws.title = "Improved Results"

    df_export = pd.DataFrame([{
        "Rank": i + 1,
        "Sum_SD": round(r["sum_sd"], 6),
        "SDs": ", ".join([f"{v:.3f}" for v in r["sds"]]),
        "Means": ", ".join([f"{v:.3f}" for v in r["means"]])
    } for i, r in enumerate(results[:topn])])

    for row in dataframe_to_rows(df_export, index=False, header=True):
        ws.append(row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    st.download_button(
        "⬇️ Excelで結果をダウンロード",
        output,
        file_name="DotBlot_Improved.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.markdown("<h3 style='text-align:center; color:#ff66b2;'>✨ あはは、できちゃった ✨</h3>", unsafe_allow_html=True)
