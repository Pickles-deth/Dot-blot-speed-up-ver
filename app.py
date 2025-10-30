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
st.set_page_config(
    page_title="Dot Blot 最適化ツール（最終版）",
    page_icon="🧪",
    layout="wide"
)

# ----------------------------------------
# ヘッダー
# ----------------------------------------
st.markdown("""
<h1 style='text-align:center; color:#2c3e50;'>🧪 Dot Blot 最適化ツール（最終版）</h1>
<p style='text-align:center; color:gray; font-size:18px;'>
条件Aを100基準に正規化し、最小SD構成を探索します。<br>
丸めなし・サンプル順序無視・再試行機能付き。
</p>
<hr style='border:1px solid #eee;'>
""", unsafe_allow_html=True)

# ----------------------------------------
# サイドバー入力
# ----------------------------------------
st.sidebar.header("⚙️ 設定")
num_rows = st.sidebar.number_input("条件（行）の数", min_value=1, max_value=10, value=4)
num_cols = st.sidebar.number_input("サンプル数（列）の数", min_value=1, max_value=10, value=4)
subset_n = st.sidebar.slider("部分探索数（条件ごとの並べ替え候補数）", 5, 50, 20, 5)
st.sidebar.markdown("---")
st.sidebar.info("各条件ごとにカンマ区切りでサンプル値を入力してください。")

# ----------------------------------------
# データ入力
# ----------------------------------------
st.markdown("### ✏️ 条件別データ入力")
cols = st.columns(2)
data = {}
for i in range(num_rows):
    key = chr(65 + i)
    with cols[i % 2]:
        values = st.text_input(f"🔹 {key}（条件{i+1}）の値", "1.0, 1.0, 1.0, 1.0")
        try:
            data[key] = [float(v.strip()) for v in values.split(",")]
        except:
            st.warning(f"{key}行の入力を確認してください。")

# ----------------------------------------
# 実行ボタン
# ----------------------------------------
run = st.button("🚀 計算を実行", type="primary", use_container_width=True)

if run:
    # ----------------------------------------
    # 関数群
    # ----------------------------------------
    def nonzero_list(row):
        return [v for v in row if v != 0.0]

    def normalize_columns(columns):
        norm = []
        for col in columns:
            base = col[0]
            if base == 0:
                norm.append(tuple(0.0 for _ in col))
            else:
                norm.append(tuple((v / base * 100) for v in col))
        return norm

    def calc_sum_sd_from_columns(columns):
        norm_cols = normalize_columns(columns)
        rows = list(zip(*norm_cols))
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
        return sum(sds), sds, means, norm_cols

    def canonicalize_columns(cols):
        return tuple(sorted(tuple(c) for c in cols))

    # ----------------------------------------
    # 前処理
    # ----------------------------------------
    nonzero_data = {k: nonzero_list(v) for k, v in data.items()}
    counts = [len(v) for v in nonzero_data.values()]
    k = min(counts)
    labels = list(nonzero_data.keys())
    st.info(f"✅ 使用サンプル数 k = {k} / 各条件の非ゼロ数: {counts}")

    # ----------------------------------------
    # 基準構成
    # ----------------------------------------
    base_cols = [tuple(nonzero_data[label][:k]) for label in labels]
    baseline_sum_sd, _, _, _ = calc_sum_sd_from_columns(base_cols)
    st.write(f"📏 基準 Sum_SD: **{baseline_sum_sd:.6f}**")

    # ----------------------------------------
    # 部分順列生成
    # ----------------------------------------
    full_perms = [list(itertools.permutations(v, k)) for v in nonzero_data.values()]
    row_perms_list = []
    for perms in full_perms:
        if len(perms) <= subset_n:
            row_perms_list.append(perms)
        else:
            row_perms_list.append(random.sample(perms, subset_n))

    total_combinations = np.prod([len(p) for p in row_perms_list])
    st.write(f"理論上の全組み合わせ数: {int(np.prod([len(p) for p in full_perms])):,} 通り")
    st.write(f"探索対象組み合わせ数（部分抽出）: **{int(total_combinations):,} 通り**")

    # ----------------------------------------
    # 探索
    # ----------------------------------------
    seen = {}
    results = []
    improved = []

    for perm_set in itertools.product(*row_perms_list):
        cols = [tuple(perm[i] for perm in perm_set) for i in range(k)]
        key = canonicalize_columns(cols)
        if key in seen:
            continue
        seen[key] = True
        sum_sd, sds, means, norm_cols = calc_sum_sd_from_columns(cols)
        results.append({
            'sum_sd': sum_sd, 'sds': sds, 'means': means, 'columns': cols, 'norm_cols': norm_cols
        })
        if sum_sd < baseline_sum_sd:
            improved.append(results[-1])

    # ----------------------------------------
    # 再試行（改善構成がない場合）
    # ----------------------------------------
    if not improved:
        st.warning("⚠️ 改善構成が見つからなかったため、残りの組み合わせで再試行します。")
        remaining_perms = []
        for full, subset in zip(full_perms, row_perms_list):
            remaining = [p for p in full if p not in subset]
            if not remaining:
                remaining = full
            remaining_perms.append(remaining)

        for perm_set in itertools.product(*remaining_perms):
            cols = [tuple(perm[i] for perm in perm_set) for i in range(k)]
            key = canonicalize_columns(cols)
            if key in seen:
                continue
            seen[key] = True
            sum_sd, sds, means, norm_cols = calc_sum_sd_from_columns(cols)
            if sum_sd < baseline_sum_sd:
                improved.append({
                    'sum_sd': sum_sd, 'sds': sds, 'means': means,
                    'columns': cols, 'norm_cols': norm_cols
                })

    # ----------------------------------------
    # 改善構成がない場合のフォールバック
    # ----------------------------------------
    if not improved:
        st.warning("⚠️ それでも改善構成は見つかりませんでした。最小SD構成を出力します。")
        best = sorted(results, key=lambda x: x["sum_sd"])[0]
        improved = [best]

    # ----------------------------------------
    # 表示
    # ----------------------------------------
    improved.sort(key=lambda x: x['sum_sd'])
    improved_ratio = len(improved) / len(results) * 100
    st.success(f"🎉 計算完了！ 改善構成数: {len(improved)}（改善率: {improved_ratio:.2f}%）")

    # 🏆 ランキング表示
    st.markdown("### 🏆 改善構成ランキング（Top 10）")
    topn = min(10, len(improved))
    sample_labels = [f"Sample{i+1}" for i in range(k)]

    for i in range(topn):
        r = improved[i]
        st.markdown(f"#### 🏅 Rank {i+1} — Sum_SD: {r['sum_sd']:.4f}")
        st.write(f"**SDs:** {', '.join(f'{v:.3f}' for v in r['sds'])}")
        st.write(f"**Means:** {', '.join(f'{v:.3f}' for v in r['means'])}")

        st.markdown("**Raw 値（行=条件 / 列=サンプル）:**")
        df_raw = pd.DataFrame(r["columns"], columns=labels, index=sample_labels).T
        st.dataframe(df_raw.style.format(precision=3), use_container_width=True)

        st.markdown("**Normalized（条件A=100基準）:**")
        df_norm = pd.DataFrame(r["norm_cols"], columns=labels, index=sample_labels).T
        st.dataframe(df_norm.style.format(precision=3), use_container_width=True)

    # ----------------------------------------
    # Excel出力
    # ----------------------------------------
    wb = Workbook()
    ws = wb.active
    ws.title = "Improved Results"

    df_export = pd.DataFrame([{
        "Rank": i + 1,
        "Sum_SD": round(r["sum_sd"], 6),
        "SDs": ", ".join([f"{v:.3f}" for v in r["sds"]]),
        "Means": ", ".join([f"{v:.3f}" for v in r["means"]])
    } for i, r in enumerate(improved[:topn])])

    if df_export.empty:
        df_export = pd.DataFrame(columns=["Rank", "Sum_SD", "SDs", "Means"])

    df_export.loc[len(df_export.index)] = ["---", "---", "---", "---"]
    df_export.loc[len(df_export.index)] = ["改善構成数", len(improved), "改善率(%)", f"{improved_ratio:.2f}"]

    for row in dataframe_to_rows(df_export, index=False, header=True):
        ws.append(row)

    output = BytesIO()
    wb.save(output)
    output.seek(0)

    st.download_button(
        "⬇️ Excelで結果をダウンロード",
        output,
        file_name="DotBlot_Improved_Results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.markdown("<h2 style='text-align:center; color:#ff66b2;'>✨ 完了！最適化構成が出ました ✨</h2>", unsafe_allow_html=True)
