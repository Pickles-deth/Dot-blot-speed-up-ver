import streamlit as st
import numpy as np
import itertools
import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.utils.dataframe import dataframe_to_rows
from joblib import Parallel, delayed

# ----------------------------------------
# 🌟 ページ設定
# ----------------------------------------
st.set_page_config(
    page_title="Dot Blot 最適化ツール",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------
# 🖼️ ロゴとタイトル
# ----------------------------------------
st.image("logo.png", width=150)
st.markdown("""
<h1 style='text-align:center; color:#2c3e50;'>🧪 Dot Blot 最適化ツール</h1>
<p style='text-align:center; color:gray; font-size:18px;'>
条件ごとのシャッフルにより最小SD構成を探索します<br>
条件（A〜D）ごとにサンプルの値を入力してください
</p>
<hr style='border:1px solid #eee;'>
""", unsafe_allow_html=True)

# ----------------------------------------
# 📥 入力
# ----------------------------------------
st.sidebar.header("⚙️ 設定")
num_rows = st.sidebar.number_input("条件の数（例：4）", min_value=1, max_value=10, value=4)
num_cols = st.sidebar.number_input("サンプル数（例：5）", min_value=1, max_value=10, value=5)
st.sidebar.markdown("---")
st.sidebar.info("各条件にカンマ区切りでサンプル値を入力してください。")

data = {}
st.markdown("### ✏️ データ入力（例：1.4, 1.2, 1.3, 0.5, 0）")
cols = st.columns(2)
for i in range(num_rows):
    key = chr(65 + i)
    with cols[i % 2]:
        values = st.text_input(f"🔹 条件 {key}", "1.0, 1.0, 1.0, 1.0, 0")
        try:
            data[key] = [float(v.strip()) for v in values.split(",")]
        except:
            st.warning(f"条件 {key} の入力を確認してください。")

# ----------------------------------------
# 🚀 実行ボタン
# ----------------------------------------
run = st.button("🚀 計算を実行する", use_container_width=True, type="primary")

if run:
    # ---------- 内部関数 ----------
    def nonzero_list(row):
        return [v for v in row if v != 0.0]

    def normalize_columns(columns):
        """
        各サンプル（列）ごとに条件Aを100基準で正規化
        columns: ndarray shape (条件数, サンプル数)
        """
        normalized = np.zeros_like(columns, dtype=float)
        base_vals = columns[0, :]  # 条件A（行0）の値を基準にする
        for j in range(columns.shape[1]):  # 各サンプル列ごとに正規化
            base = base_vals[j]
            if base == 0:
                normalized[:, j] = 0
            else:
                normalized[:, j] = columns[:, j] / base * 100
        return normalized

    def calc_sum_sd(columns):
        """columns: ndarray shape (条件数, サンプル数)"""
        normalized = normalize_columns(columns)
        means = np.nanmean(normalized, axis=1)
        sds = np.nanstd(normalized, axis=1, ddof=1)
        return np.nansum(sds), sds, means, normalized

    # ---------- 前処理 ----------
    nonzero_data = {k: nonzero_list(v) for k, v in data.items()}
    counts = [len(v) for v in nonzero_data.values()]
    k = min(counts)
    st.info(f"✅ 使用サンプル数（k）={k} / 非ゼロ数: {counts}")

    row_perms_list = [np.array(list(itertools.permutations(v, k))) for v in nonzero_data.values()]
    total_combinations = np.prod([len(p) for p in row_perms_list])
    st.write(f"全組み合わせ数: **{int(total_combinations):,}** 通り")

    labels = list(nonzero_data.keys())

    # ---------- 並列処理 ----------
    def process_perm_set(idx_tuple):
        perm_indices = np.array(idx_tuple)
        columns = np.vstack([row_perms_list[r][i] for r, i in enumerate(perm_indices)])
        if np.any(columns == 0):
            return None
        arr_hash = hash(columns.tobytes())
        return arr_hash, calc_sum_sd(columns)

    indices_list = [range(len(p)) for p in row_perms_list]
    iterator = itertools.product(*indices_list)
    seen = set()
    results = []

    total = int(total_combinations)
    chunk_size = max(total // 100, 1000)

    def chunked(it, size):
        it = iter(it)
        while True:
            chunk = list(itertools.islice(it, size))
            if not chunk:
                break
            yield chunk

    progress = st.progress(0)
    processed = 0

    for chunk in chunked(iterator, chunk_size):
        res_chunk = Parallel(n_jobs=-1, backend="loky")(
            delayed(process_perm_set)(perm_set) for perm_set in chunk
        )
        for r in res_chunk:
            if r is None:
                continue
            h, (sum_sd, sds, means, norm_cols) = r
            if h in seen:
                continue
            seen.add(h)
            results.append({
                'sum_sd': sum_sd, 'sds': sds, 'means': means, 'columns': norm_cols
            })
        processed += len(chunk)
        progress.progress(min(processed / total, 1.0))

    progress.empty()
    results.sort(key=lambda x: x['sum_sd'])
    st.success("🎉 計算が完了しました！")

    # ---------- 表示（Top10） ----------
    st.markdown("### 🏆 上位ランキング（Top 10）")
    topn = min(10, len(results))
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for i in range(topn):
        r = results[i]
        with st.expander(f"🏅 Rank {i+1} — Sum_SD: {r['sum_sd']:.4f}"):
            st.write(f"**SDs:** {', '.join(f'{v:.3f}' for v in r['sds'])}")
            st.write(f"**Means:** {', '.join(f'{v:.3f}' for v in r['means'])}")
            df_cols = pd.DataFrame(r["columns"], index=labels).T
            styled_df = df_cols.style.format(precision=3)
            for j, label in enumerate(labels):
                styled_df = styled_df.set_properties(
                    subset=[label],
                    **{
                        "color": "white",
                        "background-color": colors[j % len(colors)],
                        "font-weight": "bold",
                        "text-align": "center"
                    }
                )
            st.dataframe(styled_df, use_container_width=True)

    # ---------- Excel出力 ----------
    wb = Workbook()
    ws = wb.active
    ws.title = "Top Results"

    df = pd.DataFrame([{
        "Rank": i + 1,
        "Sum_SD": round(r["sum_sd"], 6),
        "SDs": ", ".join([f"{v:.3f}" for v in r["sds"]]),
        "Means": ", ".join([f"{v:.3f}" for v in r["means"]]),
    } for i, r in enumerate(results[:topn])])

    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)

    chart = BarChart()
    chart.title = "Sum_SD 比較"
    chart.x_axis.title = "Rank"
    chart.y_axis.title = "Sum_SD"
    data_ref = Reference(ws, min_col=2, min_row=1, max_row=len(df)+1)
    cats_ref = Reference(ws, min_col=1, min_row=2, max_row=len(df)+1)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    ws.add_chart(chart, "H3")

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    st.download_button(
        "⬇️ Excelで結果をダウンロード",
        output,
        file_name="DotBlot_Result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.markdown("<h2 style='text-align:center; color:#ff66b2;'>✨ ahaha!できちゃったよ ✨</h2>", unsafe_allow_html=True)
