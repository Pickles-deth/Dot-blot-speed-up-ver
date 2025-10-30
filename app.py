import streamlit as st
import numpy as np
import itertools
import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# ----------------------------------------
# 🌟 ページ設定
# ----------------------------------------
st.set_page_config(
    page_title="Dot Blot 最適化ツール（最終安定版）",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.image("logo.png", width=150)
st.markdown("""
<h1 style='text-align:center; color:#2c3e50;'>🧪 Dot Blot 最適化ツール（最終安定版）</h1>
<p style='text-align:center; color:gray; font-size:18px;'>
サンプル順序を無視して最小SD構成を探索します<br>
条件Aを常に100基準で正規化します
</p>
<hr style='border:1px solid #eee;'>
""", unsafe_allow_html=True)

# ----------------------------------------
# 📥 入力エリア
# ----------------------------------------
st.sidebar.header("⚙️ 設定")
num_rows = st.sidebar.number_input("条件（行）の数", min_value=2, max_value=10, value=4)
num_cols = st.sidebar.number_input("サンプル数（列）の数", min_value=2, max_value=10, value=4)
st.sidebar.markdown("---")

st.sidebar.info("各条件ごとに、カンマ区切りでサンプル値を入力してください。")

data = {}
st.markdown("### ✏️ 条件別データ入力")
cols = st.columns(2)
for i in range(num_rows):
    key = chr(65 + i)
    with cols[i % 2]:
        values = st.text_input(f"🔹 {key}（条件{i+1}）の値", "1.0, 1.0, 1.0, 0")
        try:
            data[key] = [float(v.strip()) for v in values.split(",")]
        except:
            st.warning(f"{key}の入力を確認してください。")

# ----------------------------------------
# 🚀 実行
# ----------------------------------------
run = st.button("🚀 計算を実行する", use_container_width=True, type="primary")

if run:
    def nonzero_list(row):
        return [v for v in row if v != 0.0]

    def normalize_by_A(df):
        df_norm = df.copy()
        base = df.iloc[0]  # 条件Aの値を基準に
        for col in df.columns:
            df_norm[col] = (df[col] / base[col]) * 100 if base[col] != 0 else np.nan
        return df_norm

    def calc_sum_sd_from_columns(columns):
        df_raw = pd.DataFrame(columns)
        df_norm = normalize_by_A(df_raw)
        rows = list(zip(*df_norm.values))
        sds, means = [], []
        for r in rows:
            arr = np.array([x for x in r if not np.isnan(x)])
            if arr.size == 0:
                means.append(0.0); sds.append(0.0)
            elif arr.size == 1:
                means.append(float(arr[0])); sds.append(0.0)
            else:
                means.append(float(np.mean(arr)))
                sds.append(float(np.std(arr, ddof=1)))
        return sum(sds), sds, means, df_raw, df_norm

    def canonicalize_columns(cols):
        return tuple(sorted(tuple(c) for c in cols))  # サンプル順序を無視

    # ----------------------------------------
    # 前処理
    # ----------------------------------------
    nonzero_data = {k: nonzero_list(v) for k, v in data.items()}
    counts = [len(v) for v in nonzero_data.values()]
    k = min(counts)

    st.info(f"✅ 使用サンプル数 k = {k} / 各条件の非ゼロ数: {counts}")

    row_perms_list = [list(itertools.permutations(v, k)) for v in nonzero_data.values()]
    total_combinations = np.prod([len(p) for p in row_perms_list])
    st.write(f"理論上の全組み合わせ数: **{int(total_combinations):,}** 通り")

    seen = {}
    results = []
    progress = st.progress(0)
    checked = 0

    for perm_set in itertools.product(*row_perms_list):
        checked += 1
        if checked % 1000 == 0:
            progress.progress(min(checked / total_combinations, 1.0))

        cols = [tuple(perm[i] for perm in perm_set) for i in range(k)]
        if any(0.0 in col for col in cols):
            continue

        key = canonicalize_columns(cols)
        if key in seen:
            continue

        sum_sd, sds, means, df_raw, df_norm = calc_sum_sd_from_columns(cols)
        seen[key] = True
        results.append({
            'sum_sd': sum_sd, 'sds': sds, 'means': means,
            'raw': df_raw, 'norm': df_norm
        })

    progress.empty()
    results.sort(key=lambda x: x['sum_sd'])

    st.success(f"🎉 計算完了！ 重複除外後の実際の組み合わせ数: **{len(results):,}**")

    # ----------------------------------------
    # 🏆 結果表示
    # ----------------------------------------
    st.markdown("### 🏆 上位10組み合わせ（Sum_SD昇順）")
    topn = min(10, len(results))
    labels = list(nonzero_data.keys())

    for i in range(topn):
        r = results[i]
        st.subheader(f"🏅 Rank {i+1} — Sum_SD: {r['sum_sd']:.6f}")
        st.write(f"**SDs:** {', '.join(f'{v:.3f}' for v in r['sds'])}")
        st.write(f"**Means:** {', '.join(f'{v:.3f}' for v in r['means'])}")
        st.write("**Raw 値:**")
        st.dataframe(r["raw"].style.format(precision=3), use_container_width=True)
        st.write("**Normalized（条件A=100基準）:**")
        st.dataframe(r["norm"].style.format(precision=3), use_container_width=True)

    # ----------------------------------------
    # 📊 Excel 出力
    # ----------------------------------------
    wb = Workbook()
    ws = wb.active
    ws.title = "Top10"

    df = pd.DataFrame([{
        "Rank": i + 1,
        "Sum_SD": r["sum_sd"],
        "SDs": ", ".join([f"{v:.4f}" for v in r["sds"]]),
        "Means": ", ".join([f"{v:.4f}" for v in r["means"]]),
    } for i, r in enumerate(results[:topn])])

    for row in dataframe_to_rows(df, index=False, header=True):
        ws.append(row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    st.download_button(
        "⬇️ Excel で結果をダウンロード",
        output,
        file_name="DotBlot_Final_v2.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.markdown("<h2 style='text-align:center; color:#ff66b2;'>✨ 条件A基準の最終版が完成しました ✨</h2>", unsafe_allow_html=True)
