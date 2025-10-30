# 探索1回目
improved = [r for r in results if r['sum_sd'] < baseline_sum_sd]

if not improved:
    st.warning("⚠️ 改善構成が見つからなかったため、残りの組み合わせで再試行します。")

    remaining_perms = []
    for row, perms in zip(nonzero_data.keys(), full_permutation_list):
        used = set(row_perms_list[nonzero_data.keys().index(row)])
        remain = [p for p in perms if p not in used]
        remaining_perms.append(remain)

    # 再探索（2回目）
    for perm_set in itertools.product(*remaining_perms):
        cols = [tuple(perm[i] for perm in perm_set) for i in range(k)]
        key = canonicalize_columns(cols)
        if key in seen:
            continue
        sum_sd, sds, means, norm_cols = calc_sum_sd_from_columns(cols)
        seen[key] = True
        if sum_sd < baseline_sum_sd:
            improved.append({'sum_sd': sum_sd, 'sds': sds, 'means': means, 'columns': cols, 'norm_cols': norm_cols})

if not improved:
    st.warning("⚠️ それでも改善構成は見つかりませんでした。最小SD構成を出力します。")
    best = sorted(results, key=lambda x: x["sum_sd"])[0]
    improved = [best]
