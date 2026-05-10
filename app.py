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
    xl = pd.ExcelFile(file)
    sheet_names = xl.sheet_names

    df_team = pd.read_excel(xl, sheet_name='全試合データ_チーム', header=0)
    df_player = pd.read_excel(xl, sheet_name='全試合データ_選手', header=0)
    df_team.columns = [str(c).replace('\n', '') for c in df_team.columns]
    df_player.columns = [str(c).replace('\n', '') for c in df_player.columns]
    for col in df_team.columns[5:]:
        df_team[col] = pd.to_numeric(df_team[col], errors='coerce')
    for col in df_player.columns[7:]:
        df_player[col] = pd.to_numeric(df_player[col], errors='coerce')

    extra = {}

    # AE・DE
    if 'AE・DE' in sheet_names:
        df_ae = pd.read_excel(xl, sheet_name='AE・DE', header=None)
        ae_rows = []
        group_map = {
            2:'East A',3:'East A',4:'East A',5:'East A',6:'East A',7:'East A',8:'East A',9:'East A',10:'East A',11:'East A',
            14:'East B',15:'East B',16:'East B',17:'East B',18:'East B',19:'East B',20:'East B',21:'East B',22:'East B',23:'East B',
            26:'West A',27:'West A',28:'West A',29:'West A',30:'West A',31:'West A',32:'West A',33:'West A',34:'West A',35:'West A',
            38:'West B',39:'West B',40:'West B',41:'West B',42:'West B',43:'West B',44:'West B',45:'West B',46:'West B',47:'West B'
        }
        for idx, group in group_map.items():
            if idx >= len(df_ae): continue
            row = df_ae.iloc[idx]
            try:
                ae_rows.append({
                    'グループ': group, 'リーグ順位': row[2], 'チーム名': str(row[3]),
                    '得点': pd.to_numeric(row[5], errors='coerce'),
                    '失点': pd.to_numeric(row[7], errors='coerce'),
                    'xG': pd.to_numeric(row[9], errors='coerce'),
                    'GOAL-xG': pd.to_numeric(row[11], errors='coerce'),
                    'xG/試合': pd.to_numeric(row[13], errors='coerce'),
                    'xGA': pd.to_numeric(row[15], errors='coerce'),
                    '失点-xGA': pd.to_numeric(row[17], errors='coerce'),
                    'xGA/試合': pd.to_numeric(row[19], errors='coerce'),
                    'AE': pd.to_numeric(row[21], errors='coerce'),
                    'DE': pd.to_numeric(row[23], errors='coerce'),
                    'AE-DE': pd.to_numeric(row[25], errors='coerce'),
                })
            except: pass
        extra['ae_de'] = pd.DataFrame(ae_rows)

    # グループ別行インデックス
    group_rows = {'East A':(2,11),'East B':(14,23),'West A':(26,35),'West B':(38,47)}

    def parse_group_sheet(sheet, cols, col_names):
        if sheet not in sheet_names: return pd.DataFrame()
        df = pd.read_excel(xl, sheet_name=sheet, header=None)
        rows = []
        for group, (r1, r2) in group_rows.items():
            for i in range(r1, min(r2+1, len(df))):
                row = df.iloc[i]
                team = row[cols[0]]
                if pd.isna(team) or str(team) in ['nan','NaN','East A','East B','West A','West B']: continue
                d = {'グループ': group, 'チーム名': str(team)}
                for col, name in zip(cols[1:], col_names[1:]):
                    try: d[name] = pd.to_numeric(row[col], errors='coerce')
                    except: d[name] = None
                rows.append(d)
        return pd.DataFrame(rows)

    extra['shot']    = parse_group_sheet('Shot',   [3,5,7,9,11,13,15,17], ['チーム名','得点','シュート','決定率','枠内','枠内率','OP得点','SP得点'])
    extra['a_shot']  = parse_group_sheet('A-Shot', [3,5,7,9,11,13,15,17], ['チーム名','失点','被シュート','被決定率','被枠内','被枠内率','OP失点','SP失点'])
    extra['box']     = parse_group_sheet('BOX',    [3,4,6,8,10,14,16,18,29,31], ['チーム名','PA進入合計','PA進入0-15','PA進入16-30','PA進入31-45','PA進入46-60','PA進入61-75','PA進入76-90','NZ総数','NZ/試合'])
    extra['a_box']   = parse_group_sheet('A-BOX',  [3,4,6,8,10,14,16,18,29,31], ['チーム名','被PA進入合計','被PA進入0-15','被PA進入16-30','被PA進入31-45','被PA進入46-60','被PA進入61-75','被PA進入76-90','被NZ総数','被NZ/試合'])
    extra['pass_df'] = parse_group_sheet('Pass',   [1,2,4,6,8,12,14,18,20,24,26,28,30], ['チーム名','パス総数','1試合平均','DTパス','DT成功率','MTパス','MT成功率','ATパス','AT成功率','ショートパス','ショート成功率','ミドルパス','ミドル成功率'])
    extra['cross_df']= parse_group_sheet('Cross',  [1,2,4,6,8,10,12,14,16,18,20,22,24,26], ['チーム名','クロス総数','1試合平均','成功数','成功率','右クロス','右成功数','左クロス','左成功数','PA内クロス','PA内成功数','PA内成功率','クロスシュート','クロス得点'])
    extra['def_df']  = parse_group_sheet('Defencive',[1,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30], ['チーム名','タックル総数','奪取率','DTタックル','DT奪取率','MTタックル','MT奪取率','ATタックル','AT奪取率','ATMT合計','クリア','PA内クリア','ブロック','シュートブロック','インターセプト','こぼれ球奪取'])

    # APT
    if 'APT' in sheet_names:
        df_apt = pd.read_excel(xl, sheet_name='APT', header=None)
        apt_group_rows = {'East A':(2,11),'East B':(13,22),'West A':(24,33),'West B':(35,44)}
        apt_rows = []
        for group, (r1, r2) in apt_group_rows.items():
            for i in range(r1, min(r2+1, len(df_apt))):
                row = df_apt.iloc[i]
                team = row[1]
                if pd.isna(team) or str(team) in ['nan','East A','East B','West A','West B']: continue
                apt_rows.append({
                    'グループ': group, 'チーム名': str(team),
                    '保持率': pd.to_numeric(row[2], errors='coerce'),
                    '相手陣保持割合': pd.to_numeric(row[8], errors='coerce'),
                })
        extra['apt'] = pd.DataFrame(apt_rows)

    return df_team, df_player, extra

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

    df_team, df_player, extra = load_data(uploaded_file)
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
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10 = st.tabs([
    "📊 チーム比較", "⚽ シュート分析", "🎯 パス・ポゼッション", "🏃 選手分析", "📈 時系列トレンド",
    "🧠 AE・DE分析", "📦 PA進入分析", "🏃 パス詳細", "✂️ クロス分析", "🛡️ 守備分析"
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

    # ===== 全選手集計 =====
    player_all = df_player_filtered.groupby(['選手名', 'チーム名', 'ポジション']).agg(
        出場時間=('出場時間', 'sum'),
        ゴール=('ゴール', 'sum'),
        シュート=('シュート', 'sum'),
        枠内シュート=('枠内シュート', 'sum'),
        アシスト=('アシスト', 'sum'),
        パス総数=('パス総数', 'sum'),
        パス成功数=('パス成功数', 'sum'),
        ドリブル総数=('ドリブル総数', 'sum'),
        ドリブル成功数=('ドリブル成功数', 'sum'),
        タックル総数=('タックル総数', 'sum'),
        タックル奪取数=('タックル奪取数', 'sum'),
        空中戦勝ち数=('空中戦勝ち数', 'sum'),
        クリア=('クリア', 'sum'),
        インターセプト=('インターセプト', 'sum'),
        セーブ=('セーブ', 'sum'),
        スプリント回数=('スプリント回数', 'sum'),
    ).reset_index()

    player_all['90分換算ゴール'] = (player_all['ゴール'] / player_all['出場時間'].replace(0, np.nan) * 90).round(2)
    player_all['90分換算シュート'] = (player_all['シュート'] / player_all['出場時間'].replace(0, np.nan) * 90).round(2)
    player_all['パス成功率'] = (player_all['パス成功数'] / player_all['パス総数'].replace(0, np.nan) * 100).round(1)
    player_all['枠内率'] = (player_all['枠内シュート'] / player_all['シュート'].replace(0, np.nan) * 100).round(1)
    player_all['タックル成功率'] = (player_all['タックル奪取数'] / player_all['タックル総数'].replace(0, np.nan) * 100).round(1)

    # ===== ポジション別指標定義 =====
    pos_metrics = {
        'GK': ['セーブ', 'クリア', 'パス成功率', '出場時間'],
        'DF': ['タックル奪取数', 'クリア', 'インターセプト', '空中戦勝ち数', 'パス成功率'],
        'MF': ['パス成功率', 'アシスト', 'ドリブル成功数', 'スプリント回数', 'ゴール'],
        'FW': ['ゴール', 'シュート', '90分換算ゴール', 'アシスト', '枠内率'],
    }

    # ===== フォーメーション定義（DF人数, MF人数, FW人数） =====
    formations = {
        '4-4-2': {'DF': 4, 'MF': 4, 'FW': 2},
        '4-3-3': {'DF': 4, 'MF': 3, 'FW': 3},
        '4-2-3-1': {'DF': 4, 'MF': 5, 'FW': 1},
        '3-4-3': {'DF': 3, 'MF': 4, 'FW': 3},
        '3-5-2': {'DF': 3, 'MF': 5, 'FW': 2},
        '5-3-2': {'DF': 5, 'MF': 3, 'FW': 2},
    }

    # ===== コントロール =====
    col1, col2, col3 = st.columns(3)
    with col1:
        formation = st.selectbox("フォーメーション", list(formations.keys()))
    with col2:
        min_minutes_f = st.number_input("最低出場時間（分）", min_value=0, value=90, step=10, key='f_min')
    with col3:
        # ポジション別指標をまとめて選択できるよう代表指標を表示
        rank_labels = {
            'GK': ['セーブ', 'クリア', 'パス成功率'],
            'DF': ['タックル奪取数', 'クリア', 'インターセプト', '空中戦勝ち数', 'パス成功率'],
            'MF': ['パス成功率', 'アシスト', 'ドリブル成功数', 'スプリント回数', 'ゴール'],
            'FW': ['ゴール', 'シュート', '90分換算ゴール', 'アシスト', '枠内率'],
        }
        gk_metric = st.selectbox("GKランキング指標", rank_labels['GK'])

    col1, col2, col3 = st.columns(3)
    with col1:
        df_metric = st.selectbox("DFランキング指標", rank_labels['DF'])
    with col2:
        mf_metric = st.selectbox("MFランキング指標", rank_labels['MF'])
    with col3:
        fw_metric = st.selectbox("FWランキング指標", rank_labels['FW'])

    pos_metric_map = {'GK': gk_metric, 'DF': df_metric, 'MF': mf_metric, 'FW': fw_metric}

    # ===== フォーメーション可視化関数 =====
    def build_formation_fig(formation_name, player_df, min_min, metric_map):
        form = formations[formation_name]
        n_df = form['DF']
        n_mf = form['MF']
        n_fw = form['FW']

        # 最低出場時間フィルター
        df_f = player_df[player_df['出場時間'] >= min_min].copy()

        fig = go.Figure()

        # ピッチ背景
        # 外枠
        fig.add_shape(type='rect', x0=0, y0=0, x1=100, y1=100,
                      line=dict(color='white', width=2), fillcolor='#2d8a4e')
        # センターライン
        fig.add_shape(type='line', x0=0, y0=50, x1=100, y1=50,
                      line=dict(color='white', width=1.5))
        # センターサークル
        fig.add_shape(type='circle', x0=40, y0=40, x1=60, y1=60,
                      line=dict(color='white', width=1.5))
        # ペナルティエリア（上）
        fig.add_shape(type='rect', x0=20, y0=78, x1=80, y1=100,
                      line=dict(color='white', width=1.5), fillcolor='rgba(0,0,0,0)')
        # ペナルティエリア（下）
        fig.add_shape(type='rect', x0=20, y0=0, x1=80, y1=22,
                      line=dict(color='white', width=1.5), fillcolor='rgba(0,0,0,0)')

        # ポジション別座標（y=0が自陣ゴール、y=100が相手ゴール）
        pos_coords = {
            'GK': [(50, 5)],
            'DF': [(100 / (n_df + 1) * (i + 1), 22) for i in range(n_df)],
            'MF': [(100 / (n_mf + 1) * (i + 1), 50) for i in range(n_mf)],
            'FW': [(100 / (n_fw + 1) * (i + 1), 78) for i in range(n_fw)],
        }

        colors = {'GK': '#FFD700', 'DF': '#4FC3F7', 'MF': '#81C784', 'FW': '#EF5350'}

        for pos, coords in pos_coords.items():
            metric = metric_map[pos]
            if metric not in df_f.columns:
                continue
            top = df_f[df_f['ポジション'] == pos].nlargest(len(coords), metric)

            for i, (x, y) in enumerate(coords):
                if i < len(top):
                    row = top.iloc[i]
                    name = row['選手名']
                    team = row['チーム名']
                    val = row[metric]
                    label = f"<b>{name}</b><br>{team}<br>{metric}: {val}"
                else:
                    name = '---'
                    label = '---'

                # 円マーカー
                fig.add_trace(go.Scatter(
                    x=[x], y=[y],
                    mode='markers+text',
                    marker=dict(size=30, color=colors[pos], line=dict(color='white', width=2)),
                    text=[name[:4] if name != '---' else ''],
                    textposition='middle center',
                    textfont=dict(size=9, color='black'),
                    hovertext=[label],
                    hoverinfo='text',
                    showlegend=(i == 0),
                    name=pos,
                    legendgroup=pos,
                    marker_symbol='circle',
                ))

                # 名前ラベル（円の下）
                if name != '---':
                    fig.add_annotation(
                        x=x, y=y - 6,
                        text=f"<b>{name}</b><br><span style='font-size:9px'>{team}</span><br><span style='color:#FFD700'>{metric}: {val}</span>",
                        showarrow=False,
                        font=dict(size=8, color='white'),
                        align='center',
                        bgcolor='rgba(0,0,0,0.55)',
                        bordercolor='rgba(255,255,255,0.3)',
                        borderwidth=1,
                        borderpad=2,
                    )

        fig.update_layout(
            title=dict(text=f'フォーメーション {formation_name}　指標：{" / ".join([f"{p}:{m}" for p,m in metric_map.items()])}', font=dict(color='white', size=13)),
            xaxis=dict(range=[-5, 105], showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(range=[-15, 108], showgrid=False, zeroline=False, showticklabels=False, scaleanchor='x', scaleratio=1.4),
            plot_bgcolor='#2d8a4e',
            paper_bgcolor='#1a1a2e',
            height=620,
            margin=dict(l=10, r=10, t=50, b=10),
            legend=dict(font=dict(color='white'), bgcolor='rgba(0,0,0,0.4)', bordercolor='white', borderwidth=1),
        )
        return fig

    fig_formation = build_formation_fig(formation, player_all, min_minutes_f, pos_metric_map)
    st.plotly_chart(fig_formation, use_container_width=True)
    st.caption("※ 各ポジションの上位選手を指定指標でランキングして表示しています。ホバーで詳細確認できます。")

    # ===== ランキングテーブル =====
    st.markdown("### 🏆 ポジション別ランキング")
    tabs_pos = st.tabs(['GK', 'DF', 'MF', 'FW'])
    for tab_p, pos in zip(tabs_pos, ['GK', 'DF', 'MF', 'FW']):
        with tab_p:
            metric = pos_metric_map[pos]
            df_pos = player_all[
                (player_all['ポジション'] == pos) &
                (player_all['出場時間'] >= min_minutes_f)
            ].nlargest(20, metric)[['選手名', 'チーム名', '出場時間', metric]]
            st.dataframe(df_pos.reset_index(drop=True), use_container_width=True)

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

# ===== タブ6: AE・DE分析 =====
with tab6:
    st.markdown("## 🧠 攻撃効率(AE)・守備効率(DE)分析")
    st.caption("AE = 得点/xG（1以上 → xGより多く得点）、DE = xGA/失点（1以上 → xGAより少ない失点）")

    df_ae = extra.get('ae_de', pd.DataFrame())
    if df_ae.empty:
        st.warning("AE・DEシートが見つかりません。2026_J2J3.xlsxをアップロードしてください。")
    else:
        groups = ['East A', 'East B', 'West A', 'West B']
        sel_groups = st.multiselect("グループを選択", groups, default=groups)
        df_ae_f = df_ae[df_ae['グループ'].isin(sel_groups)].copy()

        col1, col2 = st.columns(2)
        with col1:
            # AE vs DE 散布図
            fig = px.scatter(
                df_ae_f, x='AE', y='DE',
                color='グループ', text='チーム名',
                size='得点', hover_data=['xG','xGA','AE-DE'],
                title='AE vs DE マップ（右上＝攻守ともに効率的）',
                labels={'AE':'攻撃効率(AE)','DE':'守備効率(DE)'},
                height=500
            )
            fig.update_traces(textposition='top center')
            # 基準線
            fig.add_hline(y=1, line_dash='dash', line_color='gray', opacity=0.5)
            fig.add_vline(x=1, line_dash='dash', line_color='gray', opacity=0.5)
            fig.add_annotation(x=1.6, y=1.7, text="攻守効率↑", showarrow=False, font=dict(color='green'))
            fig.add_annotation(x=0.5, y=0.5, text="攻守効率↓", showarrow=False, font=dict(color='red'))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # AE-DE バーチャート
            df_ae_sorted = df_ae_f.sort_values('AE-DE', ascending=True)
            df_ae_sorted['色'] = df_ae_sorted['AE-DE'].apply(lambda x: 'positive' if x >= 0 else 'negative')
            fig2 = px.bar(
                df_ae_sorted, x='AE-DE', y='チーム名',
                orientation='h', color='色',
                color_discrete_map={'positive':'#2ecc71','negative':'#e74c3c'},
                title='AE-DE（プラス＝攻撃偏重、マイナス＝守備偏重）',
                height=500
            )
            fig2.add_vline(x=0, line_color='white', line_width=1)
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            # xG vs 得点
            fig3 = px.scatter(
                df_ae_f, x='xG', y='得点',
                color='グループ', text='チーム名',
                title='xG vs 実得点（対角線より上＝xG以上に得点）',
                height=420
            )
            fig3.update_traces(textposition='top center')
            max_v = max(df_ae_f['xG'].max(), df_ae_f['得点'].max()) + 2
            fig3.add_shape(type='line', x0=0, y0=0, x1=max_v, y1=max_v, line=dict(dash='dash', color='gray'))
            st.plotly_chart(fig3, use_container_width=True)

        with col2:
            # xGA vs 失点
            fig4 = px.scatter(
                df_ae_f, x='xGA', y='失点',
                color='グループ', text='チーム名',
                title='xGA vs 実失点（対角線より下＝xGA以上に守れている）',
                height=420
            )
            fig4.update_traces(textposition='top center')
            max_v2 = max(df_ae_f['xGA'].max(), df_ae_f['失点'].max()) + 2
            fig4.add_shape(type='line', x0=0, y0=0, x1=max_v2, y1=max_v2, line=dict(dash='dash', color='gray'))
            st.plotly_chart(fig4, use_container_width=True)

        # データテーブル
        st.markdown("### 📋 AE・DEデータ一覧")
        display_cols = ['グループ','チーム名','得点','失点','xG','GOAL-xG','xGA','失点-xGA','AE','DE','AE-DE']
        df_show = df_ae_f[display_cols].sort_values(['グループ','AE-DE'], ascending=[True,False])
        st.dataframe(
            df_show.style
            .background_gradient(subset=['AE'], cmap='RdYlGn')
            .background_gradient(subset=['DE'], cmap='RdYlGn')
            .format({'AE':'{:.3f}','DE':'{:.3f}','AE-DE':'{:.3f}','xG':'{:.2f}','xGA':'{:.2f}',
                     'GOAL-xG':'{:.2f}','失点-xGA':'{:.2f}'}),
            use_container_width=True
        )

# ===== タブ7: PA進入分析 =====
with tab7:
    st.markdown("## 📦 PA進入・ニアゾーン進入分析")

    df_box   = extra.get('box', pd.DataFrame())
    df_a_box = extra.get('a_box', pd.DataFrame())

    if df_box.empty:
        st.warning("BOX/A-BOXシートが見つかりません。")
    else:
        groups = ['East A', 'East B', 'West A', 'West B']
        sel_g = st.multiselect("グループを選択", groups, default=groups, key='box_group')
        df_box_f   = df_box[df_box['グループ'].isin(sel_g)].copy()
        df_a_box_f = df_a_box[df_a_box['グループ'].isin(sel_g)].copy()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                df_box_f.sort_values('PA進入合計', ascending=True),
                x='PA進入合計', y='チーム名', orientation='h',
                color='グループ', title='PA進入合計（攻撃）',
                height=max(400, len(df_box_f)*22)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.bar(
                df_a_box_f.sort_values('被PA進入合計', ascending=False),
                x='被PA進入合計', y='チーム名', orientation='h',
                color='グループ', title='被PA進入合計（守備）←少ないほど良い',
                height=max(400, len(df_a_box_f)*22)
            )
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        # PA進入 vs 被PA進入 散布図
        merged = df_box_f[['チーム名','グループ','PA進入合計','NZ総数']].merge(
            df_a_box_f[['チーム名','被PA進入合計','被NZ総数']], on='チーム名', how='inner')
        fig3 = px.scatter(
            merged, x='PA進入合計', y='被PA進入合計',
            color='グループ', text='チーム名',
            title='PA進入 vs 被PA進入（左下＝攻守バランス良、右上＝攻守ともに多い）',
            size='NZ総数', height=480
        )
        fig3.update_traces(textposition='top center')
        st.plotly_chart(fig3, use_container_width=True)

        # 時間帯別PA進入ヒートマップ（攻撃）
        st.markdown("### ⏱️ 時間帯別PA進入ヒートマップ（攻撃）")
        time_cols = ['PA進入0-15','PA進入16-30','PA進入31-45','PA進入46-60','PA進入61-75','PA進入76-90']
        pivot = df_box_f.set_index('チーム名')[time_cols].fillna(0)
        pivot.columns = ['0-15','16-30','31-45','46-60','61-75','76-90']
        fig4 = px.imshow(pivot, color_continuous_scale='Blues',
                         title='時間帯別PA進入数（攻撃）', aspect='auto', height=max(350, len(pivot)*22))
        st.plotly_chart(fig4, use_container_width=True)

        # 時間帯別被PA進入ヒートマップ（守備）
        st.markdown("### ⏱️ 時間帯別PA進入ヒートマップ（守備）")
        a_time_cols = ['被PA進入0-15','被PA進入16-30','被PA進入31-45','被PA進入46-60','被PA進入61-75','被PA進入76-90']
        pivot2 = df_a_box_f.set_index('チーム名')[a_time_cols].fillna(0)
        pivot2.columns = ['0-15','16-30','31-45','46-60','61-75','76-90']
        fig5 = px.imshow(pivot2, color_continuous_scale='Reds',
                         title='時間帯別被PA進入数（守備）', aspect='auto', height=max(350, len(pivot2)*22))
        st.plotly_chart(fig5, use_container_width=True)

# ===== タブ8: パス詳細 =====
with tab8:
    st.markdown("## 🏃 パス詳細分析")

    df_pass = extra.get('pass_df', pd.DataFrame())
    df_apt  = extra.get('apt', pd.DataFrame())

    if df_pass.empty:
        st.warning("Passシートが見つかりません。")
    else:
        groups = ['East A', 'East B', 'West A', 'West B']
        sel_g = st.multiselect("グループを選択", groups, default=groups, key='pass_group')
        df_pass_f = df_pass[df_pass['グループ'].isin(sel_g)].copy()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                df_pass_f.sort_values('パス総数', ascending=True),
                x='パス総数', y='チーム名', orientation='h',
                color='グループ', title='パス総数ランキング',
                height=max(400, len(df_pass_f)*22)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # パス総数 vs 1試合平均
            fig2 = px.scatter(
                df_pass_f, x='1試合平均', y='ショート成功率',
                color='グループ', text='チーム名',
                size='パス総数',
                title='1試合平均パス数 vs ショートパス成功率',
                height=420
            )
            fig2.update_traces(textposition='top center')
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        st.markdown("### エリア別パス内訳")
        # DT/MT/ATパス内訳
        area_cols = ['DTパス','MTパス','ATパス']
        area_data = df_pass_f[['チーム名','グループ'] + area_cols].melt(
            id_vars=['チーム名','グループ'], var_name='エリア', value_name='パス数')
        fig3 = px.bar(area_data, x='チーム名', y='パス数', color='エリア',
                      barmode='stack', title='エリア別パス数（DT=守備/MT=中盤/AT=攻撃）',
                      height=420)
        fig3.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### パス長さ別内訳")
        len_cols = ['ショートパス','ミドルパス','ミドル成功率']
        col1, col2 = st.columns(2)
        with col1:
            len_data = df_pass_f[['チーム名','グループ','ショートパス','ミドルパス']].melt(
                id_vars=['チーム名','グループ'], var_name='種別', value_name='パス数')
            fig4 = px.bar(len_data, x='チーム名', y='パス数', color='種別',
                          barmode='group', title='ショート vs ミドルパス数',
                          height=400)
            fig4.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig4, use_container_width=True)

        with col2:
            if not df_apt.empty:
                df_apt_f = df_apt[df_apt['グループ'].isin(sel_g)]
                fig5 = px.bar(
                    df_apt_f.sort_values('保持率', ascending=True),
                    x='保持率', y='チーム名', orientation='h',
                    color='グループ', title='ボール保持率',
                    height=max(400, len(df_apt_f)*22)
                )
                fig5.update_xaxes(tickformat='.1%')
                st.plotly_chart(fig5, use_container_width=True)

        # データテーブル
        st.markdown("### 📋 パス詳細データ")
        st.dataframe(df_pass_f.sort_values(['グループ','パス総数'], ascending=[True,False]).reset_index(drop=True), use_container_width=True)

# ===== タブ9: クロス分析 =====
with tab9:
    st.markdown("## ✂️ クロス詳細分析")

    df_cross = extra.get('cross_df', pd.DataFrame())
    if df_cross.empty:
        st.warning("Crossシートが見つかりません。")
    else:
        groups = ['East A', 'East B', 'West A', 'West B']
        sel_g = st.multiselect("グループを選択", groups, default=groups, key='cross_group')
        df_cross_f = df_cross[df_cross['グループ'].isin(sel_g)].copy()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.scatter(
                df_cross_f, x='クロス総数', y='成功率',
                color='グループ', text='チーム名',
                size='クロス得点',
                title='クロス数 vs 成功率（バブル＝クロスからの得点数）',
                height=450
            )
            fig.update_traces(textposition='top center')
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # 右左クロス比較
            side_data = df_cross_f[['チーム名','グループ','右クロス','左クロス']].melt(
                id_vars=['チーム名','グループ'], var_name='サイド', value_name='クロス数')
            fig2 = px.bar(side_data, x='チーム名', y='クロス数', color='サイド',
                          barmode='group', title='左右サイドクロス比較',
                          height=450)
            fig2.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            # クロス得点効率
            df_cross_f['クロス得点率'] = df_cross_f['クロス得点'] / df_cross_f['クロス総数'].replace(0, np.nan)
            fig3 = px.bar(
                df_cross_f.sort_values('クロス得点率', ascending=True),
                x='クロス得点率', y='チーム名', orientation='h',
                color='グループ', title='クロスから得点になる確率',
                height=max(400, len(df_cross_f)*22)
            )
            fig3.update_xaxes(tickformat='.1%')
            st.plotly_chart(fig3, use_container_width=True)

        with col2:
            # PA内クロス成功率
            fig4 = px.bar(
                df_cross_f.sort_values('PA内成功率', ascending=True),
                x='PA内成功率', y='チーム名', orientation='h',
                color='グループ', title='PA内クロス成功率',
                height=max(400, len(df_cross_f)*22)
            )
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown("### 📋 クロスデータ一覧")
        st.dataframe(df_cross_f.sort_values(['グループ','クロス総数'], ascending=[True,False]).reset_index(drop=True), use_container_width=True)

# ===== タブ10: 守備分析 =====
with tab10:
    st.markdown("## 🛡️ 守備詳細分析")

    df_def = extra.get('def_df', pd.DataFrame())
    if df_def.empty:
        st.warning("Defenciveシートが見つかりません。")
    else:
        groups = ['East A', 'East B', 'West A', 'West B']
        sel_g = st.multiselect("グループを選択", groups, default=groups, key='def_group')
        df_def_f = df_def[df_def['グループ'].isin(sel_g)].copy()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                df_def_f.sort_values('タックル総数', ascending=True),
                x='タックル総数', y='チーム名', orientation='h',
                color='グループ', title='タックル総数',
                height=max(400, len(df_def_f)*22)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig2 = px.scatter(
                df_def_f, x='タックル総数', y='奪取率',
                color='グループ', text='チーム名',
                title='タックル数 vs 奪取率',
                height=420
            )
            fig2.update_traces(textposition='top center')
            fig2.update_yaxes(tickformat='.1%')
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        st.markdown("### エリア別タックル内訳")
        area_data = df_def_f[['チーム名','グループ','DTタックル','MTタックル','ATタックル']].melt(
            id_vars=['チーム名','グループ'], var_name='エリア', value_name='タックル数')
        fig3 = px.bar(area_data, x='チーム名', y='タックル数', color='エリア',
                      barmode='stack', title='エリア別タックル数（DT=守備/MT=中盤/AT=攻撃）',
                      height=420)
        fig3.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### 守備プレー比較")
        col1, col2 = st.columns(2)
        with col1:
            fig4 = px.bar(
                df_def_f.sort_values('クリア', ascending=True),
                x='クリア', y='チーム名', orientation='h',
                color='グループ', title='クリア数ランキング',
                height=max(400, len(df_def_f)*22)
            )
            st.plotly_chart(fig4, use_container_width=True)

        with col2:
            fig5 = px.bar(
                df_def_f.sort_values('インターセプト', ascending=True),
                x='インターセプト', y='チーム名', orientation='h',
                color='グループ', title='インターセプト数ランキング',
                height=max(400, len(df_def_f)*22)
            )
            st.plotly_chart(fig5, use_container_width=True)

        # レーダーチャート（守備指標上位5チーム）
        st.markdown("### 守備レーダーチャート")
        top5_teams = df_def_f.nlargest(5, 'タックル総数')['チーム名'].tolist()
        radar_metrics = ['タックル総数','クリア','インターセプト','シュートブロック','こぼれ球奪取']
        radar_df = df_def_f[df_def_f['チーム名'].isin(top5_teams)].copy()
        for m in radar_metrics:
            mn, mx = radar_df[m].min(), radar_df[m].max()
            radar_df[f'{m}_n'] = ((radar_df[m] - mn) / (mx - mn + 1e-9) * 100).fillna(0)

        fig6 = go.Figure()
        colors = px.colors.qualitative.Set2
        for i, team in enumerate(top5_teams):
            row = radar_df[radar_df['チーム名'] == team]
            if row.empty: continue
            vals = [float(row[f'{m}_n'].values[0]) for m in radar_metrics]
            vals += vals[:1]
            fig6.add_trace(go.Scatterpolar(
                r=vals, theta=radar_metrics + radar_metrics[:1],
                fill='toself', name=team,
                line_color=colors[i % len(colors)], opacity=0.7
            ))
        fig6.update_layout(
            title='守備指標レーダーチャート（タックル数上位5チーム）',
            polar=dict(radialaxis=dict(visible=True, range=[0,100])),
            height=450
        )
        st.plotly_chart(fig6, use_container_width=True)

        st.markdown("### 📋 守備データ一覧")
        st.dataframe(df_def_f.sort_values(['グループ','タックル総数'], ascending=[True,False]).reset_index(drop=True), use_container_width=True)

# フッター
st.markdown('---')
st.caption('J2/J3 2026シーズン イベントデータ分析ツール | Powered by Streamlit & Plotly')
