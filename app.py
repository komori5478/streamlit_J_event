import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(
    page_title="J2/J3 イベントデータ分析",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #1a1a2e;
        text-align: center;
        padding: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data(file):
    df_team = pd.read_excel(file, sheet_name='全試合データ_チーム', header=0)
    df_player = pd.read_excel(file, sheet_name='全試合データ_選手', header=0)

    df_team.columns = [str(c).replace('\n', '') for c in df_team.columns]
    df_player.columns = [str(c).replace('\n', '') for c in df_player.columns]

    for col in df_team.columns[5:]:
        df_team[col] = pd.to_numeric(df_team[col], errors='coerce')
    for col in df_player.columns[7:]:
        df_player[col] = pd.to_numeric(df_player[col], errors='coerce')

    return df_team, df_player

# ===== サイドバー =====
with st.sidebar:
    st.markdown("## ⚽ J2/J3 分析ツール")
    st.markdown("---")
    st.markdown("### 📁 データ読み込み")
    uploaded_file = st.file_uploader("XLSXファイルをアップロード", type=["xlsx"])

    if not uploaded_file:
        st.info("👆 Excelファイルをアップロードしてください")
        st.markdown("""
        **必要なシート構成：**
        - `全試合データ_チーム`
        - `全試合データ_選手`
        """)
        st.stop()

    df_team, df_player = load_data(uploaded_file)
    st.success(f"✅ 読み込み完了")
    st.caption(f"チームデータ: {len(df_team)}行 / 選手データ: {len(df_player)}行")

    st.markdown("---")
    st.markdown("### 🔍 フィルター")
    all_teams = sorted(df_team['チーム名'].dropna().unique())
    selected_teams = st.multiselect("チームを選択", all_teams, default=all_teams[:6])

    rounds = sorted(df_team['節'].dropna().unique().astype(int))
    selected_rounds = st.slider(
        "節の範囲",
        int(min(rounds)), int(max(rounds)),
        (int(min(rounds)), int(max(rounds)))
    )

# ===== データフィルタリング =====
if not selected_teams:
    st.warning("サイドバーでチームを選択してください")
    st.stop()

df_filtered = df_team[
    (df_team['チーム名'].isin(selected_teams)) &
    (df_team['節'] >= selected_rounds[0]) &
    (df_team['節'] <= selected_rounds[1])
].copy()

df_player_filtered = df_player[df_player['チーム名'].isin(selected_teams)].copy()

# ===== メインヘッダー =====
st.markdown('<div class="main-header">⚽ J2/J3 2026 イベントデータ分析</div>', unsafe_allow_html=True)
st.caption(f"表示中: {', '.join(selected_teams)} ／ 第{selected_rounds[0]}節〜第{selected_rounds[1]}節")

# ===== タブ =====
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 チーム比較", "⚽ シュート分析", "🎯 パス・ポゼッション", "🏃 選手分析", "📈 時系列トレンド"
])

# ===== タブ1: チーム比較 =====
with tab1:
    st.markdown("## チーム総合比較")

    team_agg = df_filtered.groupby('チーム名').agg(
        得点=('得点', 'sum'),
        失点=('失点', 'sum'),
        シュート=('シュート', 'sum'),
        枠内シュート=('枠内シュート', 'sum'),
        xG=('xG', 'sum'),
        パス総数=('パス総数', 'sum'),
        パス成功数=('パス成功数', 'sum'),
        ドリブル総数=('ドリブル総数', 'sum'),
        ドリブル成功数=('ドリブル成功数', 'sum'),
        タックル総数=('タックル総数', 'sum'),
        タックル奪取数=('タックル奪取数', 'sum'),
    ).reset_index()

    team_agg['得失点差'] = team_agg['得点'] - team_agg['失点']
    team_agg['シュート枠内率'] = (team_agg['枠内シュート'] / team_agg['シュート'].replace(0, np.nan) * 100).round(1)
    team_agg['パス成功率'] = (team_agg['パス成功数'] / team_agg['パス総数'].replace(0, np.nan) * 100).round(1)
    team_agg['ドリブル成功率'] = (team_agg['ドリブル成功数'] / team_agg['ドリブル総数'].replace(0, np.nan) * 100).round(1)

    # KPI
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🥇 最多得点チーム", team_agg.loc[team_agg['得点'].idxmax(), 'チーム名'], f"{team_agg['得点'].max()}点")
    col2.metric("📐 最高xG", team_agg.loc[team_agg['xG'].idxmax(), 'チーム名'], f"{team_agg['xG'].max():.1f}")
    col3.metric("🎯 最高パス成功率", team_agg.loc[team_agg['パス成功率'].idxmax(), 'チーム名'], f"{team_agg['パス成功率'].max():.1f}%")
    col4.metric("⚡ 最多シュート", team_agg.loc[team_agg['シュート'].idxmax(), 'チーム名'], f"{team_agg['シュート'].max()}本")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        fig = px.scatter(
            team_agg, x='xG', y='得点',
            text='チーム名', size='シュート',
            color='得失点差', color_continuous_scale='RdYlGn',
            title='得点 vs xG（バブルサイズ = シュート数）',
            height=430
        )
        fig.update_traces(textposition='top center', marker=dict(opacity=0.8))
        max_val = max(team_agg['xG'].max(), team_agg['得点'].max())
        fig.add_shape(type='line', x0=0, y0=0, x1=max_val, y1=max_val,
                      line=dict(dash='dash', color='gray'))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        teams_radar = team_agg['チーム名'].tolist()[:6]
        metrics = ['シュート枠内率', 'パス成功率', 'ドリブル成功率']
        radar_data = team_agg[team_agg['チーム名'].isin(teams_radar)].copy()
        for m in metrics:
            min_v, max_v = radar_data[m].min(), radar_data[m].max()
            radar_data[f'{m}_norm'] = ((radar_data[m] - min_v) / (max_v - min_v + 1e-9) * 100).fillna(0)

        fig_radar = go.Figure()
        colors = px.colors.qualitative.Set2
        for i, team in enumerate(teams_radar):
            row = radar_data[radar_data['チーム名'] == team]
            if row.empty:
                continue
            values = [float(row[f'{m}_norm'].values[0]) for m in metrics]
            values += values[:1]
            fig_radar.add_trace(go.Scatterpolar(
                r=values, theta=metrics + metrics[:1],
                fill='toself', name=team,
                line_color=colors[i % len(colors)], opacity=0.7
            ))
        fig_radar.update_layout(
            title='チーム能力レーダーチャート',
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            height=430
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    metric_option = st.selectbox("棒グラフの指標", ['得点', '失点', 'xG', 'シュート', 'パス総数', 'ドリブル総数'])
    fig_bar = px.bar(
        team_agg.sort_values(metric_option, ascending=True),
        x=metric_option, y='チーム名', orientation='h',
        color=metric_option, color_continuous_scale='Blues',
        title=f'チーム別 {metric_option}', height=380
    )
    st.plotly_chart(fig_bar, use_container_width=True)

# ===== タブ2: シュート分析 =====
with tab2:
    st.markdown("## シュート・ゴール分析")

    col1, col2 = st.columns(2)
    with col1:
        # PA内外シュート
        pa_data = df_filtered.groupby('チーム名').agg(
            PA内シュート=('PA内シュート', 'sum'),
            PA外シュート=('PA外シュート', 'sum'),
            PA内ゴール=('PA内ゴール', 'sum'),
            PA外ゴール=('PA外ゴール', 'sum'),
        ).reset_index()

        fig = go.Figure()
        fig.add_trace(go.Bar(name='PA内シュート', x=pa_data['チーム名'], y=pa_data['PA内シュート'], marker_color='#2196F3'))
        fig.add_trace(go.Bar(name='PA外シュート', x=pa_data['チーム名'], y=pa_data['PA外シュート'], marker_color='#FF9800'))
        fig.update_layout(barmode='stack', title='PA内外シュート数', xaxis_tickangle=-45, height=400)
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.histogram(
            df_filtered[df_filtered['xG'] > 0],
            x='xG', color='チーム名',
            barmode='overlay', opacity=0.7,
            title='試合別 xG 分布',
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

    # シュートパターン
    shot_pattern_cols = [c for c in df_team.columns if 'シュートパターン' in c]
    if shot_pattern_cols:
        shot_patterns = df_filtered.groupby('チーム名')[shot_pattern_cols].sum()
        shot_patterns.columns = [c.replace('シュートパターン', '').strip() for c in shot_patterns.columns]
        fig = px.bar(
            shot_patterns.reset_index().melt(id_vars='チーム名'),
            x='チーム名', y='value', color='variable',
            title='シュートパターン内訳（積み上げ）',
            labels={'value': 'シュート数', 'variable': 'パターン'},
            height=400
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

# ===== タブ3: パス・ポゼッション =====
with tab3:
    st.markdown("## パス・ポゼッション分析")

    col1, col2 = st.columns(2)
    with col1:
        pass_data = df_filtered.groupby('チーム名').agg(
            パス総数=('パス総数', 'sum'),
            パス成功数=('パス成功数', 'sum'),
            ボール保持率=('ボール保持率', 'mean'),
            クロス総数=('クロス総数', 'sum'),
        ).reset_index()
        pass_data['パス成功率'] = (pass_data['パス成功数'] / pass_data['パス総数'].replace(0, np.nan) * 100).round(1)
        pass_data['保持率(%)'] = (pass_data['ボール保持率'] * 100).round(1)

        fig = px.scatter(
            pass_data, x='保持率(%)', y='パス成功率',
            text='チーム名', size='パス総数',
            color='クロス総数', color_continuous_scale='Viridis',
            title='ボール保持率 vs パス成功率',
            height=420
        )
        fig.update_traces(textposition='top center')
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        cross_data = df_filtered.groupby('チーム名').agg(
            右サイドからのクロス=('右サイドからのクロス', 'sum'),
            左サイドからのクロス=('左サイドからのクロス', 'sum'),
        ).reset_index()
        side_data = cross_data.melt(id_vars='チーム名')
        side_data['variable'] = side_data['variable'].str.replace('サイドからのクロス', '')
        fig = px.bar(side_data, x='チーム名', y='value', color='variable',
                     barmode='group', title='左右サイドクロス比較',
                     labels={'value': 'クロス数', 'variable': 'サイド'},
                     height=420)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

    # ゾーン別パス
    zone_data = []
    for zone, col in [('DT（守備）', 'DTからのパス'), ('MT（中盤）', 'MTからのパス'), ('AT（攻撃）', 'ATからのパス')]:
        if col in df_filtered.columns:
            for team, val in df_filtered.groupby('チーム名')[col].sum().items():
                zone_data.append({'チーム名': team, 'ゾーン': zone, 'パス数': val})
    if zone_data:
        zone_df = pd.DataFrame(zone_data)
        fig = px.bar(zone_df, x='チーム名', y='パス数', color='ゾーン',
                     title='ゾーン別パス数（積み上げ）', barmode='stack', height=380)
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

# ===== タブ4: 選手分析 =====
with tab4:
    st.markdown("## 選手パフォーマンス分析")

    col1, col2 = st.columns([1, 3])
    with col1:
        positions = ['全て'] + sorted(df_player_filtered['ポジション'].dropna().unique().tolist())
        selected_pos = st.selectbox("ポジション", positions)
        min_minutes = st.number_input("最低出場時間（分）", min_value=0, value=90, step=10)

    df_p = df_player_filtered.copy()
    if selected_pos != '全て':
        df_p = df_p[df_p['ポジション'] == selected_pos]
    df_p = df_p[df_p['出場時間'] >= min_minutes]

    player_agg = df_p.groupby(['選手名', 'チーム名', 'ポジション']).agg(
        出場時間=('出場時間', 'sum'),
        ゴール=('ゴール', 'sum'),
        シュート=('シュート', 'sum'),
        枠内シュート=('枠内シュート', 'sum'),
        アシスト=('アシスト', 'sum'),
        パス総数=('パス総数', 'sum'),
        パス成功数=('パス成功数', 'sum'),
        ドリブル総数=('ドリブル総数', 'sum'),
        ドリブル成功数=('ドリブル成功数', 'sum'),
    ).reset_index()

    player_agg['90分換算ゴール'] = (player_agg['ゴール'] / player_agg['出場時間'].replace(0, np.nan) * 90).round(2)
    player_agg['90分換算シュート'] = (player_agg['シュート'] / player_agg['出場時間'].replace(0, np.nan) * 90).round(2)
    player_agg['パス成功率'] = (player_agg['パス成功数'] / player_agg['パス総数'].replace(0, np.nan) * 100).round(1)
    player_agg['枠内率'] = (player_agg['枠内シュート'] / player_agg['シュート'].replace(0, np.nan) * 100).round(1)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.scatter(
            player_agg, x='ゴール', y='アシスト',
            color='チーム名', symbol='ポジション',
            hover_name='選手名', size='出場時間',
            title='ゴール vs アシスト', height=430
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.scatter(
            player_agg[player_agg['シュート'] >= 2],
            x='90分換算シュート', y='枠内率',
            color='チーム名', hover_name='選手名',
            size='ゴール',
            title='90分換算シュート vs 枠内率（シュート2本以上）',
            height=430
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 🏆 選手ランキング")
    col1, col2 = st.columns(2)
    with col1:
        rank_col = st.selectbox("ランキング指標", ['ゴール', 'アシスト', 'シュート', '90分換算ゴール', 'パス成功率', 'ドリブル成功数'])
    with col2:
        top_n = st.slider("表示人数", 5, 30, 10)

    top_players = player_agg.nlargest(top_n, rank_col)[['選手名', 'チーム名', 'ポジション', '出場時間', rank_col]]
    st.dataframe(top_players.reset_index(drop=True), use_container_width=True)

# ===== タブ5: 時系列トレンド =====
with tab5:
    st.markdown("## 時系列トレンド分析")

    col1, col2 = st.columns(2)
    with col1:
        metric_trend = st.selectbox(
            "指標を選択",
            ['得点', '失点', 'xG', 'シュート', 'パス成功数', 'ドリブル成功数', '枠内シュート']
        )
    with col2:
        show_cumulative = st.checkbox("累積値で表示", value=True)

    trend_data = df_filtered.groupby(['節', 'チーム名'])[metric_trend].sum().reset_index()

    if show_cumulative:
        trend_data = trend_data.sort_values(['チーム名', '節'])
        trend_data['表示値'] = trend_data.groupby('チーム名')[metric_trend].cumsum()
        title = f'累積 {metric_trend} の推移'
    else:
        trend_data['表示値'] = trend_data[metric_trend]
        title = f'節別 {metric_trend} の推移'

    fig = px.line(
        trend_data, x='節', y='表示値',
        color='チーム名', markers=True,
        title=title,
        labels={'節': '節', '表示値': metric_trend},
        height=420
    )
    fig.update_xaxes(dtick=1)
    st.plotly_chart(fig, use_container_width=True)

    # ヒートマップ
    pivot_data = trend_data.pivot(index='チーム名', columns='節', values=metric_trend).fillna(0)
    fig_hm = px.imshow(
        pivot_data,
        title=f'節別 {metric_trend} ヒートマップ',
        color_continuous_scale='YlOrRd',
        labels=dict(x='節', y='チーム名', color=metric_trend),
        height=400, aspect='auto'
    )
    st.plotly_chart(fig_hm, use_container_width=True)

# フッター
st.markdown("---")
st.caption("J2/J3 2026シーズン イベントデータ分析ツール | Powered by Streamlit & Plotly")
