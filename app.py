import streamlit as st
import numpy as np
import itertools
import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.chart import BarChart, Reference
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
# 🖼️ タイトル
# ----------------------------------------
st.markdown("""
<h1 style='text-align:center; color:#2c3e50;'>🧪 Dot Blot 最適化ツール — Sum_SD グループ化版</h1>
<p style='text-align:center; color:gray; font-size:18px;'>
条件ごとのシャッフルから最小SD構成を探索し、同型パターンと同一SD値を統合します
</p>
<hr style='border:1px solid #eee;'>
""", unsafe_allow_html=True)

# ----------------------------------------
# 📥 入力設定
# ----------------------------------------
st.sidebar.header("⚙️ 設定")
num_rows = st.sidebar.number_input("条件の数（例：4）", min_value=1, max_value=10, value=4)
num_cols = st.sidebar.number_input("サンプル数（例：5）", min_value=1, max_value=10, value=5)

st.sidebar.info("各条件にカンマ区切りでサンプル値を入力（0 は除外）")

data = {}
st.markdown("### ✏️ データ入力")
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
    def nonzero_list(row):
        return [v for v in row if v != 0.0]

    def normalize_columns(columns):
        """各サンプル列ごとに条件Aを100基準で正規化"""
        normalized = np.zeros_like(columns, dtype=float)
        base_vals = columns[0, :]
        for j in range(columns.shape[1]):
            base = base_vals[j]
            normalized[:, j] = columns[:, j] / base * 100 if base != 0 else 0
        return normalized

    def calc_sum_sd(columns):
        normalized = normalize_columns(columns)
        means = np.nanmean(normalized, axis=1)
        sds = np.nanstd(normalized, axis=1, ddof=1)
        return np.nansum(sds), sds, means, normalized

    # ----------------------------------------
    # 前処理
    # ----------------------------------------
    nonzero_data = {k: nonzero_list(v) for k, v in data.items()}
    counts = [len(v) for v in nonzero_data.values()]
    k = min(counts)
    st.info(f"✅ 使用サンプル数（k）={k} / 非ゼロ数: {counts}")

    row_perms_list = [np.array(list(itertools.permutations(v, k))) for v in nonzero_data.values()]
    total_combinations = np.prod([len(p) for p in row_perms_list])
    st.write(f"全組み合わせ数（理論値）: **{int(total_combinations):,}** 通り")

    labels = list(nonzero_data.keys())

    # ----------------------------------------
    # 並列計算（重複削除あり）
    # ----------------------------------------
    def process_perm_set(idx_tuple):
        perm_indices = np.array(idx_tuple)
        columns = np.vstack([row_perms_list[r][i] for r, i in enumerate(perm_indices)])
        if np.any(columns == 0):
            return None
        # 同型（サンプル順入れ替え）重複を排除
        sorted_cols = np.sort(columns, axis=1)
        arr_hash = hash(sorted_cols.tobytes())
        return arr_hash, columns, calc_sum_sd(columns)

    indices_list = [range(len(p)) for p in row_perms_list]
    iterator = itertools.product(*indices_list)
    seen = set()
    results = []

    progress = st.progress(0)
    total = int(total_combinations)
    processed = 0
    chunk_size = max(total // 100, 1000)

    def chunked(it, size):
        it = iter(it)
        while True:
            chunk = list(itertools.islice(it, size))
            if not chunk:
                break
            yield chunk

    for chunk in chunked(iterator, chunk_size):
        res_chunk = Parallel(n_jobs=-1, backend="loky")(
            delayed(process_perm_set)(perm_set) for perm_set in chunk
        )
        for r in res_chunk:
            if r is None:
                continue
            h, raw_cols, (sum_sd, sds, means, norm_cols) = r
            if h in seen:
                continue
            seen.add(h)
            results.append({
                'sum_sd': round(sum_sd, 6),
                'sds': sds,
                'means': means,
                'columns': norm_cols,
                'raw': raw_cols
            })
        processed += len(chunk)
        progress.progress(min(processed / total, 1.0))

    progress.empty()
    st.success(f"🎉 計算が完了しました！ 結果数: {len(results):,}")

    # ----------------------------------------
    # Sum_SD ごとにグループ化
    # ----------------------------------------
    grouped = {}
    for r in results:
        grouped.setdefault(r['sum_sd'], []).append(r)

    sorted_groups = sorted(grouped.items(), key=lambda x: x[0])
    st.markdown("### 🏆 Sum_SD ごとのグループ一覧")

    for rank, (sum_sd, group) in enumerate(sorted_groups[:10], start=1):
        with st.expander(f"🏅 Group {rank} — Sum_SD: {sum_sd:.6f}（{len(group)} 組）"):
            for j, r in enumerate(group, start=1):
                st.markdown(f"#### 組み合わせ {j}")
                st.write(f"**SDs:** {', '.join(f'{v:.3f}' for v in r['sds'])}")
                st.write(f"**Means:** {', '.join(f'{v:.3f}' for v in r['means'])}")
                st.markdown("**🔹 生データ（Raw）**")
                st.dataframe(pd.DataFrame(r["raw"], index=labels).T.style.format(precision=3),
                             use_container_width=True)
                st.markdown("**🔹 正規化データ（A=100基準）**")
                st.dataframe(pd.DataFrame(r["columns"], index=labels).T.style.format(precision=3),
                             use_container_width=True)

    # ----------------------------------------
    # Excel 出力
    # ----------------------------------------
    wb = Workbook()
    ws_summary = wb.active
    ws_summary.title = "Summary"
    ws_summary.append(["Rank", "Sum_SD", "組み合わせ数"])
    for i, (sum_sd, group) in enumerate(sorted_groups, start=1):
        ws_summary.append([i, sum_sd, len(group)])

    chart = BarChart()
    chart.title = "Sum_SD 分布"
    chart.x_axis.title = "Rank"
    chart.y_axis.title = "Sum_SD"
    data_ref = Reference(ws_summary, min_col=2, min_row=1, max_row=len(sorted_groups)+1)
    cats_ref = Reference(ws_summary, min_col=1, min_row=2, max_row=len(sorted_groups)+1)
    chart.add_data(data_ref, titles_from_data=True)
    chart.set_categories(cats_ref)
    ws_summary.add_chart(chart, "E3")

    for i, (sum_sd, group) in enumerate(sorted_groups[:10], start=1):
        wsn = wb.create_sheet(f"SumSD_{sum_sd:.6f}")
        for j, r in enumerate(group, start=1):
            wsn.append([f"組み合わせ {j}"])
            wsn.append(["Raw Data"])
            for row in dataframe_to_rows(pd.DataFrame(r["raw"], index=labels).T, index=True, header=True):
                wsn.append(row)
            wsn.append([])
            wsn.append(["Normalized (A=100)"])
            for row in dataframe_to_rows(pd.DataFrame(r["columns"], index=labels).T, index=True, header=True):
                wsn.append(row)
            wsn.append([])

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    st.download_button(
        "⬇️ Excelで結果をダウンロード（Sum_SDグループ化）",
        output,
        file_name="DotBlot_Grouped_Result.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.markdown("<h3 style='text-align:center; color:#ff66b2;'>✨ 同じSD値をまとめてグループ化完了 ✨</h3>", unsafe_allow_html=True)
