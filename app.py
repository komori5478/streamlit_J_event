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
def load_master(team_file, player_file, league='J2/J3'):
    df_tm = pd.read_csv(team_file, encoding='cp932')
    df_pm = pd.read_csv(player_file, encoding='cp932')

    # リーグに応じてIDを切り替え（J1=249, J2/J3=250）
    league_id = 249 if league == 'J1' else 250
    target = df_tm[df_tm['試合種別ID'] == league_id].copy()

    def parse_color(c):
        try:
            r, g, b = str(c).split('.')
            return f'rgb({int(float(r))},{int(float(g))},{int(float(b))})'
        except:
            return 'rgb(128,128,128)'

    team_master = target[['チームID','チーム名略','所属グループ','チームカラー','チーム名']].copy()
    team_master.columns = ['チームID','チーム名','グループ','チームカラー生','チームフルネーム']
    team_master['チームカラー'] = team_master['チームカラー生'].apply(parse_color)
    team_master = team_master.drop(columns=['チームカラー生'])

    target_ids = target['チームID'].tolist()
    player_master = df_pm[df_pm['チームID'].isin(target_ids)][
        ['選手ID','選手名','チーム名略','ポジション','背番号','身長','体重','生年月日',
         'Jリーグ通算出場数(J1)','Jリーグ通算出場数(J2)','Jリーグ通算出場数(J3)']
    ].copy()
    player_master.columns = ['選手ID','選手名','チーム名','ポジション','背番号','身長','体重','生年月日',
                              'J1通算','J2通算','J3通算']
    player_master['生年月日'] = pd.to_numeric(player_master['生年月日'], errors='coerce')
    player_master['年齢'] = player_master['生年月日'].apply(
        lambda x: 2026 - int(str(int(x))[:4]) if pd.notna(x) else None
    )
    player_master['Jリーグ通算'] = (
        player_master['J1通算'].fillna(0) +
        player_master['J2通算'].fillna(0) +
        player_master['J3通算'].fillna(0)
    ).astype(int)

    return team_master, player_master

@st.cache_data
def load_data(file):
    xl = pd.ExcelFile(file)

    df_team = pd.read_excel(xl, sheet_name='全試合データ_チーム', header=0)
    df_player = pd.read_excel(xl, sheet_name='全試合データ_選手', header=0)
    df_team.columns = [str(c).replace('\n', '') for c in df_team.columns]
    df_player.columns = [str(c).replace('\n', '') for c in df_player.columns]
    for col in df_team.columns[5:]:
        df_team[col] = pd.to_numeric(df_team[col], errors='coerce')
    for col in df_player.columns[7:]:
        df_player[col] = pd.to_numeric(df_player[col], errors='coerce')

    extra = {}

    # ===== AE・DE をイベントデータから計算 =====
    # 相手チームのxGを自チームのxGAとして結合
    df_xga = df_team[['節','チーム名','相手チーム名','xG']].copy()
    df_xga = df_xga.rename(columns={'チーム名':'相手チーム名', '相手チーム名':'チーム名', 'xG':'xGA'})
    df_with_xga = df_team.merge(df_xga[['節','チーム名','xGA']], on=['節','チーム名'], how='left')

    ae_agg = df_with_xga.groupby('チーム名').agg(
        試合数=('節','count'),
        得点=('得点','sum'),
        失点=('失点','sum'),
        xG=('xG','sum'),
        xGA=('xGA','sum'),
    ).reset_index()

    ae_agg['GOAL-xG']  = ae_agg['得点']  - ae_agg['xG']
    ae_agg['失点-xGA'] = ae_agg['失点']  - ae_agg['xGA']
    ae_agg['xG/試合']  = ae_agg['xG']   / ae_agg['試合数']
    ae_agg['xGA/試合'] = ae_agg['xGA']  / ae_agg['試合数']
    # AE = 得点/xG, DE = xGA/失点（失点0のチームはNaN）
    ae_agg['AE']    = ae_agg['得点']  / ae_agg['xG'].replace(0, np.nan)
    ae_agg['DE']    = ae_agg['xGA']   / ae_agg['失点'].replace(0, np.nan)
    ae_agg['AE-DE'] = ae_agg['AE']   - ae_agg['DE']

    extra['ae_de'] = ae_agg

    # ===== その他集計もイベントデータから =====
    # シュート詳細
    shot_cols = ['チーム名','得点','シュート','枠内シュート','xG','PA内シュート','PA外シュート','PA内ゴール','PA外ゴール']
    available = [c for c in shot_cols if c in df_team.columns]
    shot_agg = df_team.groupby('チーム名')[available[1:]].sum().reset_index()
    shot_agg.columns = ['チーム名'] + available[1:]
    shot_agg['決定率'] = shot_agg['得点'] / shot_agg['シュート'].replace(0, np.nan)
    shot_agg['枠内率'] = shot_agg['枠内シュート'] / shot_agg['シュート'].replace(0, np.nan)
    extra['shot'] = shot_agg

    # 被シュート（相手側のシュートデータを結合）
    df_opp = df_team[['節','チーム名','相手チーム名','シュート','枠内シュート','xG','得点']].copy()
    df_opp = df_opp.rename(columns={
        'チーム名':'相手チーム名','相手チーム名':'チーム名',
        'シュート':'被シュート','枠内シュート':'被枠内シュート','xG':'xGA_match','得点':'失点_check'
    })
    a_shot_agg = df_opp.groupby('チーム名').agg(
        被シュート=('被シュート','sum'),
        被枠内シュート=('被枠内シュート','sum'),
    ).reset_index()
    a_shot_agg['被枠内率'] = a_shot_agg['被枠内シュート'] / a_shot_agg['被シュート'].replace(0, np.nan)
    extra['a_shot'] = a_shot_agg

    # PA進入
    box_cols = [c for c in df_team.columns if 'PA' in c or 'ニアゾーン' in c]
    if box_cols:
        box_agg = df_team.groupby('チーム名')[box_cols].sum().reset_index()
        extra['box'] = box_agg

    # パス詳細
    pass_cols = [c for c in df_team.columns if 'パス' in c]
    if pass_cols:
        pass_agg = df_team.groupby('チーム名')[pass_cols].sum().reset_index()
        extra['pass_df'] = pass_agg

    # クロス詳細
    cross_cols = [c for c in df_team.columns if 'クロス' in c]
    if cross_cols:
        cross_agg = df_team.groupby('チーム名')[cross_cols].sum().reset_index()
        extra['cross_df'] = cross_agg

    # 守備詳細
    def_cols = [c for c in df_team.columns if any(k in c for k in ['タックル','クリア','ブロック','インターセプト','こぼれ球'])]
    if def_cols:
        def_agg = df_team.groupby('チーム名')[def_cols].sum().reset_index()
        extra['def_df'] = def_agg

    # ===== PPDA計算 =====
    # 相手チームのDT+MTパス数（相手が自陣+中盤で行ったパス = 自チームが守備すべきゾーンのパス）
    df_ppda_opp = df_team[['節','チーム名','相手チーム名','DTからのパス','MTからのパス']].copy()
    df_ppda_opp = df_ppda_opp.rename(columns={
        'チーム名': '相手チーム名',
        '相手チーム名': 'チーム名',
        'DTからのパス': '相手DTパス',
        'MTからのパス': '相手MTパス',
    })
    df_ppda_base = df_team[['節','チーム名','ATでのタックル奪取数','MTでのタックル奪取数','インターセプト','ファウル','DTでのファウル']].copy()
    df_ppda_base = df_ppda_base.merge(df_ppda_opp[['節','チーム名','相手DTパス','相手MTパス']], on=['節','チーム名'], how='left')

    # PPDA = (相手DTパス + 相手MTパス) / (ATタックル奪取 + MTタックル奪取 + インターセプト + ファウル - DTでのファウル)
    ppda_agg = df_ppda_base.groupby('チーム名').agg(
        相手パス=( '相手MTパス', 'sum'),  # MT+DTは後で足す
        相手DTパス=('相手DTパス', 'sum'),
        ATタックル奪取=('ATでのタックル奪取数', 'sum'),
        MTタックル奪取=('MTでのタックル奪取数', 'sum'),
        インターセプト=('インターセプト', 'sum'),
        ファウル=('ファウル', 'sum'),
        DTファウル=('DTでのファウル', 'sum'),
    ).reset_index()

    ppda_agg['相手パス合計'] = ppda_agg['相手パス'] + ppda_agg['相手DTパス']
    ppda_agg['守備アクション'] = (
        ppda_agg['ATタックル奪取'] +
        ppda_agg['MTタックル奪取'] +
        ppda_agg['インターセプト'] +
        ppda_agg['ファウル'] - ppda_agg['DTファウル']  # 自陣ファウルは除外
    )
    ppda_agg['PPDA'] = (ppda_agg['相手パス合計'] / ppda_agg['守備アクション'].replace(0, np.nan)).round(2)
    extra['ppda'] = ppda_agg[['チーム名','PPDA','相手パス合計','守備アクション']]

    # ボール保持率
    if 'ボール保持率' in df_team.columns:
        apt_agg = df_team.groupby('チーム名').agg(
            保持率=('ボール保持率','mean'),
        ).reset_index()
        extra['apt'] = apt_agg

    # ===== 被チャンスクリエイト（チーム単位）=====
    # 相手チームのスルーパス成功数 + クロス成功数 + ラストパスを逆算
    cc_cols = ['スルーパス成功数','クロス成功数','ラストパス']
    cc_available = [c for c in cc_cols if c in df_team.columns]
    if cc_available:
        df_cc_opp = df_team[['節','チーム名','相手チーム名'] + cc_available].copy()
        df_cc_opp = df_cc_opp.rename(columns={'チーム名':'相手チーム名','相手チーム名':'チーム名'})
        df_cc_opp['相手CC'] = df_cc_opp[cc_available].sum(axis=1)
        cc_agg = df_cc_opp.groupby('チーム名').agg(
            被チャンスクリエイト=('相手CC','sum'),
            試合数=('節','count'),
        ).reset_index()
        cc_agg['被CC/試合'] = (cc_agg['被チャンスクリエイト'] / cc_agg['試合数']).round(1)

        # チーム自身のCCも計算して合わせる
        df_team['CC'] = df_team[cc_available].sum(axis=1)
        cc_self = df_team.groupby('チーム名').agg(チャンスクリエイト=('CC','sum')).reset_index()
        cc_agg = cc_agg.merge(cc_self, on='チーム名', how='left')
        cc_agg['CC/試合'] = (cc_agg['チャンスクリエイト'] / cc_agg['試合数']).round(1)
        cc_agg['CC差'] = cc_agg['チャンスクリエイト'] - cc_agg['被チャンスクリエイト']
        extra['cc'] = cc_agg

    return df_team, df_player, extra


@st.cache_data
def load_apt_sheet(file):
    """APTシートをグループ別に丸ごと読み込む"""
    xl = pd.ExcelFile(file)
    if 'APT' not in xl.sheet_names:
        return {}

    df = pd.read_excel(xl, sheet_name='APT', header=None)

    def fmt_time(v):
        """時間文字列から秒以下を除去してmm:ssに整形"""
        s = str(v).split('.')[0]
        return s if s not in ['nan','NaT'] else '-'

    def pct(v):
        try: return f"{float(v)*100:.1f}%"
        except: return '-'

    group_ranges = {
        'East A': (2, 11), 'East B': (13, 22),
        'West A': (24, 33), 'West B': (35, 44),
    }

    apt_data = {}
    for group, (r1, r2) in group_ranges.items():
        rows = []
        for i in range(r1, min(r2+1, len(df))):
            row = df.iloc[i]
            team = row[1]
            if pd.isna(team) or str(team) == group: continue

            rows.append({
                'チーム名':          str(team),
                'ボール保持率':      pct(row[2]),
                '保持率順位':        int(row[3]) if pd.notna(row[3]) else '-',
                'APT（分:秒）':      fmt_time(row[4]),
                'APT順位':           int(row[5]) if pd.notna(row[5]) else '-',
                'ボール保持時間':    fmt_time(row[6]),
                '相手陣保持割合':    pct(row[8]),
                '相手陣保持割合順位': int(row[9]) if pd.notna(row[9]) else '-',
                '相手陣保持時間':    fmt_time(row[10]),
                '保持率1位試合':     f"{pct(row[11])} vs {str(row[12]).split('.')[0] if pd.notna(row[12]) else '-'} ({str(row[13]).strip() if pd.notna(row[13]) else '-'}節)" if pd.notna(row[11]) else '-',
                '保持率2位試合':     f"{pct(row[14])} vs {str(row[15]).strip() if pd.notna(row[15]) else '-'} ({str(row[16]).strip() if pd.notna(row[16]) else '-'}節)" if pd.notna(row[14]) else '-',
                '保持率3位試合':     f"{pct(row[17])} vs {str(row[18]).strip() if pd.notna(row[18]) else '-'} ({str(row[19]).strip() if pd.notna(row[19]) else '-'}節)" if pd.notna(row[17]) else '-',
                '保持率4位試合':     f"{pct(row[20])} vs {str(row[21]).strip() if pd.notna(row[21]) else '-'} ({str(row[22]).strip() if pd.notna(row[22]) else '-'}節)" if pd.notna(row[20]) else '-',
                '保持率5位試合':     f"{pct(row[23])} vs {str(row[24]).strip() if pd.notna(row[24]) else '-'} ({str(row[25]).strip() if pd.notna(row[25]) else '-'}節)" if pd.notna(row[23]) else '-',
            })
        apt_data[group] = pd.DataFrame(rows)

    return apt_data

# ===== サイドバー =====
with st.sidebar:
    st.markdown("## ⚽ Jリーグ 分析ツール")
    st.markdown("---")

    # リーグ選択
    st.markdown("### 🏆 リーグ選択")
    selected_league = st.radio("リーグ", ["J1", "J2/J3"], horizontal=True)

    st.markdown("---")
    st.markdown("### 📁 データ読み込み")
    uploaded_file = st.file_uploader(
        f"{selected_league} XLSXファイルをアップロード", type=["xlsx"],
        key=f"upload_{selected_league}"
    )

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

    # 分析用ファイル（APTシート等）
    st.markdown("---")
    st.markdown("### 📁 分析データ（任意）")
    st.caption("2026_J2J3.xlsx等、APTシートを含むファイル")
    analysis_file = st.file_uploader("分析用XLSXをアップロード", type=["xlsx"], key="analysis_upload")
    apt_sheet_data = {}
    if analysis_file:
        apt_sheet_data = load_apt_sheet(analysis_file)
        if apt_sheet_data:
            st.success("✅ APTデータ読み込み完了")
        else:
            st.warning("APTシートが見つかりませんでした")

    # マスターデータ自動読み込み（リポジトリに同梱）
    team_master   = None
    player_master = None
    try:
        team_master, player_master = load_master('MasterTeam_2026.csv', 'MasterPlayer_2026.csv')
        st.success("✅ マスターデータ読み込み完了")
    except:
        st.info("ℹ️ マスターデータが見つかりません（任意）")

    # チームカラー・グループ辞書
    if team_master is not None:
        color_map = dict(zip(team_master['チーム名'], team_master['チームカラー']))
        group_map = dict(zip(team_master['チーム名'], team_master['グループ']))
    else:
        color_map = {}
        group_map = {}

    st.markdown("---")
    st.markdown("### 🔍 フィルター")
    all_teams = sorted(df_team['チーム名'].dropna().unique())

    # J2/J3のみグループフィルター表示
    if selected_league == "J2/J3" and group_map:
        all_groups = sorted(set(group_map.values()))
        sel_groups = st.multiselect("グループで絞り込み", all_groups, default=all_groups)
        teams_in_group = [t for t in all_teams if group_map.get(t,'') in sel_groups]
    else:
        teams_in_group = all_teams

    selected_teams = st.multiselect("チームを選択", teams_in_group, default=teams_in_group[:6])

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
league_label = "J1" if selected_league == "J1" else "J2/J3"
st.markdown(f'<div class="main-header">⚽ {league_label} 2026 イベントデータ分析</div>', unsafe_allow_html=True)

# グループ別チーム表示（J2/J3かつマスターあり）
if selected_league == "J2/J3" and group_map:
    grp_text = ' ／ '.join([f"**{g}**: {', '.join([t for t in selected_teams if group_map.get(t)==g])}" for g in sorted(set(group_map.get(t,'') for t in selected_teams)) if [t for t in selected_teams if group_map.get(t)==g]])
    st.caption(f"第{selected_rounds[0]}節〜第{selected_rounds[1]}節　{grp_text}")
else:
    st.caption(f"表示中: {', '.join(selected_teams)} ／ 第{selected_rounds[0]}節〜第{selected_rounds[1]}節")

# ===== タブ =====
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12 = st.tabs([
    "📊 チーム比較", "⚽ シュート分析", "🎯 パス・ポゼッション", "🏃 選手分析", "📈 時系列トレンド",
    "🧠 AE・DE分析", "📦 PA進入分析", "🏃 パス詳細", "✂️ クロス分析", "🛡️ 守備分析",
    "⏱️ APT（ボール保持）", "📋 チーム詳細レポート"
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
        pa_data['合計'] = pa_data['PA内シュート'] + pa_data['PA外シュート']
        pa_data = pa_data.sort_values('合計', ascending=False)

        fig = go.Figure()
        fig.add_trace(go.Bar(name='PA内シュート', x=pa_data['チーム名'], y=pa_data['PA内シュート'], marker_color='#2196F3'))
        fig.add_trace(go.Bar(name='PA外シュート', x=pa_data['チーム名'], y=pa_data['PA外シュート'], marker_color='#FF9800'))
        fig.update_layout(barmode='stack', title='PA内外シュート数（降順）', xaxis_tickangle=-45, height=400)
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
        shot_patterns['合計'] = shot_patterns.sum(axis=1)
        shot_patterns = shot_patterns.sort_values('合計', ascending=False).drop(columns='合計')
        fig = px.bar(
            shot_patterns.reset_index().melt(id_vars='チーム名'),
            x='チーム名', y='value', color='variable',
            title='シュートパターン内訳（降順）',
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
        cross_data['合計'] = cross_data['右サイドからのクロス'] + cross_data['左サイドからのクロス']
        cross_data = cross_data.sort_values('合計', ascending=False)
        side_data = cross_data[['チーム名','右サイドからのクロス','左サイドからのクロス']].melt(id_vars='チーム名')
        side_data['variable'] = side_data['variable'].str.replace('サイドからのクロス', '')
        fig = px.bar(side_data, x='チーム名', y='value', color='variable',
                     barmode='group', title='左右サイドクロス比較（降順）',
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
        team_order = zone_df.groupby('チーム名')['パス数'].sum().sort_values(ascending=False).index.tolist()
        zone_df['チーム名'] = pd.Categorical(zone_df['チーム名'], categories=team_order, ordered=True)
        zone_df = zone_df.sort_values('チーム名')
        fig = px.bar(zone_df, x='チーム名', y='パス数', color='ゾーン',
                     title='ゾーン別パス数（降順）', barmode='stack', height=380)
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
        ラストパス=('ラストパス', 'sum'),
        パス総数=('パス総数', 'sum'),
        パス成功数=('パス成功数', 'sum'),
        スルーパス成功数=('スルーパス成功数', 'sum'),
        クロス成功数=('クロス成功数', 'sum'),
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
    # チャンスクリエイト指数 = スルーパス成功数 + クロス成功数 + ラストパス
    player_all['チャンスクリエイト'] = (
        player_all['スルーパス成功数'] + player_all['クロス成功数'] + player_all['ラストパス']
    ).round(0)
    player_all['90分換算CC'] = (player_all['チャンスクリエイト'] / player_all['出場時間'].replace(0, np.nan) * 90).round(2)

    # ===== ポジション別指標定義 =====
    pos_metrics = {
        'GK': ['セーブ', 'クリア', 'パス成功率', '出場時間'],
        'DF': ['タックル奪取数', 'クリア', 'インターセプト', '空中戦勝ち数', 'パス成功率'],
        'MF': ['パス成功率', 'アシスト', 'ドリブル成功数', 'スプリント回数', 'ゴール', 'チャンスクリエイト'],
        'FW': ['ゴール', 'シュート', '90分換算ゴール', 'アシスト', '枠内率', 'チャンスクリエイト'],
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
        rank_labels = {
            'GK': ['セーブ', 'クリア', 'パス成功率'],
            'DF': ['タックル奪取数', 'クリア', 'インターセプト', '空中戦勝ち数', 'パス成功率'],
            'MF': ['パス成功率', 'アシスト', 'ドリブル成功数', 'スプリント回数', 'ゴール', 'チャンスクリエイト', '90分換算CC'],
            'FW': ['ゴール', 'シュート', '90分換算ゴール', 'アシスト', '枠内率', 'チャンスクリエイト', '90分換算CC'],
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

        df_f = player_df[player_df['出場時間'] >= min_min].copy()

        # 選手マスター結合（あれば）
        if player_master is not None:
            pm = player_master[['選手名','年齢','身長','背番号','Jリーグ通算']].drop_duplicates('選手名')
            df_f = df_f.merge(pm, on='選手名', how='left')

        fig = go.Figure()

        # ピッチ描画
        fig.add_shape(type='rect', x0=0, y0=0, x1=100, y1=100,
                      line=dict(color='white', width=2), fillcolor='#2d8a4e')
        fig.add_shape(type='line', x0=0, y0=50, x1=100, y1=50, line=dict(color='white', width=1.5))
        fig.add_shape(type='circle', x0=40, y0=40, x1=60, y1=60, line=dict(color='white', width=1.5))
        fig.add_shape(type='rect', x0=20, y0=78, x1=80, y1=100, line=dict(color='white', width=1.5), fillcolor='rgba(0,0,0,0)')
        fig.add_shape(type='rect', x0=20, y0=0, x1=80, y1=22, line=dict(color='white', width=1.5), fillcolor='rgba(0,0,0,0)')

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
                    val  = row[metric]

                    # マスター情報
                    age    = int(row['年齢'])    if player_master is not None and pd.notna(row.get('年齢'))    else None
                    height = int(row['身長'])    if player_master is not None and pd.notna(row.get('身長'))    else None
                    number = int(row['背番号'])  if player_master is not None and pd.notna(row.get('背番号'))  else None
                    jlg    = int(row['Jリーグ通算']) if player_master is not None and pd.notna(row.get('Jリーグ通算')) else None

                    extra_info = ''
                    if age:    extra_info += f'年齢:{age}'
                    if height: extra_info += f' / {height}cm'
                    if jlg is not None: extra_info += f' / J通算:{jlg}'

                    num_str = f'#{number} ' if number else ''
                    hover_label = f"<b>{num_str}{name}</b><br>{team}<br>{metric}: {val}"
                    if extra_info: hover_label += f"<br>{extra_info}"

                    display_name = name[:4]
                    if number: display_name = f'#{number}'
                else:
                    name = '---'
                    hover_label = '---'
                    display_name = ''

                fig.add_trace(go.Scatter(
                    x=[x], y=[y],
                    mode='markers+text',
                    marker=dict(size=30, color=colors[pos], line=dict(color='white', width=2)),
                    text=[display_name],
                    textposition='middle center',
                    textfont=dict(size=9, color='black'),
                    hovertext=[hover_label],
                    hoverinfo='text',
                    showlegend=(i == 0),
                    name=pos,
                    legendgroup=pos,
                ))

                if name != '---':
                    age_str = f' ({age}歳)' if age else ''
                    fig.add_annotation(
                        x=x, y=y - 6,
                        text=f"<b>{name}</b>{age_str}<br><span style='font-size:9px'>{team}</span><br><span style='color:#FFD700'>{metric}: {val}</span>",
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
            ].nlargest(20, metric)

            # マスター情報を結合
            if player_master is not None:
                pm = player_master[['選手名','背番号','年齢','身長','体重','Jリーグ通算']].drop_duplicates('選手名')
                df_pos = df_pos.merge(pm, on='選手名', how='left')
                show_cols = ['選手名','チーム名','背番号','年齢','身長','Jリーグ通算','出場時間', metric]
            else:
                show_cols = ['選手名','チーム名','出場時間', metric]

            show_cols = [c for c in show_cols if c in df_pos.columns]
            st.dataframe(df_pos[show_cols].reset_index(drop=True), use_container_width=True)

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
        st.warning("データが見つかりません。")
    else:
        # チームフィルター（サイドバーのselected_teamsを使用）
        df_ae_f = df_ae[df_ae['チーム名'].isin(selected_teams)].copy() if selected_teams else df_ae.copy()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.scatter(
                df_ae_f, x='AE', y='DE',
                text='チーム名',
                size='得点',
                hover_data=['xG','xGA','AE-DE','得点','失点'],
                title='AE vs DE マップ（右上＝攻守ともに効率的）',
                labels={'AE':'攻撃効率(AE)','DE':'守備効率(DE)'},
                color='AE-DE', color_continuous_scale='RdYlGn',
                height=500
            )
            fig.update_traces(textposition='top center')
            fig.add_hline(y=1, line_dash='dash', line_color='gray', opacity=0.5)
            fig.add_vline(x=1, line_dash='dash', line_color='gray', opacity=0.5)
            fig.add_annotation(x=df_ae_f['AE'].max(), y=df_ae_f['DE'].max(), text="攻守効率↑", showarrow=False, font=dict(color='green'))
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            df_ae_sorted = df_ae_f.sort_values('AE-DE', ascending=True)
            df_ae_sorted['色'] = df_ae_sorted['AE-DE'].apply(lambda x: 'プラス（攻撃偏重）' if x >= 0 else 'マイナス（守備偏重）')
            fig2 = px.bar(
                df_ae_sorted, x='AE-DE', y='チーム名',
                orientation='h', color='色',
                color_discrete_map={'プラス（攻撃偏重）':'#2ecc71','マイナス（守備偏重）':'#e74c3c'},
                title='AE-DE（プラス＝攻撃で稼ぐ、マイナス＝守備で耐える）',
                height=500
            )
            fig2.add_vline(x=0, line_color='white', line_width=1)
            st.plotly_chart(fig2, use_container_width=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            fig3 = px.scatter(
                df_ae_f, x='xG', y='得点',
                text='チーム名', color='AE',
                color_continuous_scale='RdYlGn',
                title='xG vs 実得点（対角線より上＝xG以上に得点）',
                height=420
            )
            fig3.update_traces(textposition='top center')
            max_v = max(df_ae_f['xG'].max(), df_ae_f['得点'].max()) + 2
            fig3.add_shape(type='line', x0=0, y0=0, x1=max_v, y1=max_v, line=dict(dash='dash', color='gray'))
            st.plotly_chart(fig3, use_container_width=True)

        with col2:
            fig4 = px.scatter(
                df_ae_f, x='xGA', y='失点',
                text='チーム名', color='DE',
                color_continuous_scale='RdYlGn_r',
                title='xGA vs 実失点（対角線より下＝xGAより少ない失点）',
                height=420
            )
            fig4.update_traces(textposition='top center')
            max_v2 = max(df_ae_f['xGA'].max(), df_ae_f['失点'].max()) + 2
            fig4.add_shape(type='line', x0=0, y0=0, x1=max_v2, y1=max_v2, line=dict(dash='dash', color='gray'))
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown("### 📋 AE・DEデータ一覧")
        display_cols = ['チーム名','試合数','得点','失点','xG','GOAL-xG','xGA','失点-xGA','AE','DE','AE-DE']
        available_cols = [c for c in display_cols if c in df_ae_f.columns]
        df_show = df_ae_f[available_cols].sort_values('AE-DE', ascending=False).reset_index(drop=True)
        fmt = {c: '{:.3f}' for c in ['AE','DE','AE-DE','xG','xGA','GOAL-xG','失点-xGA','xG/試合','xGA/試合'] if c in df_show.columns}
        st.dataframe(df_show.style.format(fmt), use_container_width=True)

# ===== タブ7: PA進入分析 =====
with tab7:
    st.markdown("## 📦 PA進入・ニアゾーン進入分析")

    df_box = extra.get('box', pd.DataFrame())
    if df_box.empty:
        st.warning("PA進入データが見つかりません。")
    else:
        df_box_f = df_box[df_box['チーム名'].isin(selected_teams)].copy() if selected_teams else df_box.copy()

        # PA進入関連列の特定
        pa_total_col = [c for c in df_box_f.columns if 'PA内シュート' in c or 'PA進入' in c]
        nz_col = [c for c in df_box_f.columns if 'ニアゾーン' in c]

        if pa_total_col:
            pa_col = pa_total_col[0]
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(
                    df_box_f.sort_values(pa_col, ascending=True),
                    x=pa_col, y='チーム名', orientation='h',
                    color=pa_col, color_continuous_scale='Blues',
                    title=f'{pa_col}ランキング（攻撃）',
                    height=max(400, len(df_box_f)*22)
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                if nz_col:
                    nz = nz_col[0]
                    fig2 = px.scatter(
                        df_box_f, x=pa_col, y=nz,
                        text='チーム名', color=pa_col,
                        color_continuous_scale='Viridis',
                        title=f'{pa_col} vs {nz}',
                        height=max(400, len(df_box_f)*22)
                    )
                    fig2.update_traces(textposition='top center')
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    # PA内外シュート比較
                    pa_in = [c for c in df_box_f.columns if 'PA内シュート' in c]
                    pa_out = [c for c in df_box_f.columns if 'PA外シュート' in c]
                    if pa_in and pa_out:
                        fig2 = go.Figure()
                        fig2.add_trace(go.Bar(name='PA内シュート', x=df_box_f['チーム名'], y=df_box_f[pa_in[0]], marker_color='#2196F3'))
                        fig2.add_trace(go.Bar(name='PA外シュート', x=df_box_f['チーム名'], y=df_box_f[pa_out[0]], marker_color='#FF9800'))
                        fig2.update_layout(barmode='stack', title='PA内外シュート比較', xaxis_tickangle=-45, height=400)
                        st.plotly_chart(fig2, use_container_width=True)

        st.markdown("### 📋 PA関連データ一覧")
        st.dataframe(df_box_f.reset_index(drop=True), use_container_width=True)

# ===== タブ8: パス詳細 =====
with tab8:
    st.markdown("## 🏃 パス詳細分析")

    df_pass = extra.get('pass_df', pd.DataFrame())
    df_apt  = extra.get('apt', pd.DataFrame())

    if df_pass.empty:
        st.warning("パスデータが見つかりません。")
    else:
        df_pass_f = df_pass[df_pass['チーム名'].isin(selected_teams)].copy() if selected_teams else df_pass.copy()

        col1, col2 = st.columns(2)
        with col1:
            fig = px.bar(
                df_pass_f.sort_values('パス総数', ascending=True),
                x='パス総数', y='チーム名', orientation='h',
                color='パス総数', color_continuous_scale='Blues',
                title='パス総数ランキング',
                height=max(400, len(df_pass_f)*22)
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            if 'パス成功数' in df_pass_f.columns:
                df_pass_f['パス成功率_calc'] = df_pass_f['パス成功数'] / df_pass_f['パス総数'].replace(0, np.nan)
                fig2 = px.scatter(
                    df_pass_f, x='パス総数', y='パス成功率_calc',
                    text='チーム名', color='パス成功率_calc',
                    color_continuous_scale='RdYlGn',
                    title='パス総数 vs 成功率',
                    height=420
                )
                fig2.update_traces(textposition='top center')
                fig2.update_yaxes(tickformat='.1%')
                st.plotly_chart(fig2, use_container_width=True)

        dt_col = [c for c in df_pass_f.columns if c.startswith('DT') and 'パス' in c]
        mt_col = [c for c in df_pass_f.columns if c.startswith('MT') and 'パス' in c]
        at_col = [c for c in df_pass_f.columns if c.startswith('AT') and 'パス' in c]
        if dt_col and mt_col and at_col:
            st.markdown("### エリア別パス内訳")
            area_df = df_pass_f[['チーム名', dt_col[0], mt_col[0], at_col[0]]].copy()
            area_df.columns = ['チーム名', 'DT（守備）', 'MT（中盤）', 'AT（攻撃）']
            area_data = area_df.melt(id_vars='チーム名', var_name='エリア', value_name='パス数')
            fig3 = px.bar(area_data, x='チーム名', y='パス数', color='エリア',
                          barmode='stack', title='エリア別パス数', height=420)
            fig3.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True)

        if not df_apt.empty:
            df_apt_f = df_apt[df_apt['チーム名'].isin(selected_teams)].copy() if selected_teams else df_apt.copy()
            fig4 = px.bar(
                df_apt_f.sort_values('保持率', ascending=True),
                x='保持率', y='チーム名', orientation='h',
                color='保持率', color_continuous_scale='Blues',
                title='ボール保持率（平均）',
                height=max(400, len(df_apt_f)*22)
            )
            fig4.update_xaxes(tickformat='.1%')
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown("### 📋 パス詳細データ")
        st.dataframe(df_pass_f.sort_values('パス総数', ascending=False).reset_index(drop=True), use_container_width=True)

# ===== タブ9: クロス分析 =====
with tab9:
    st.markdown("## ✂️ クロス詳細分析")

    df_cross = extra.get('cross_df', pd.DataFrame())
    if df_cross.empty:
        st.warning("クロスデータが見つかりません。")
    else:
        df_cross_f = df_cross[df_cross['チーム名'].isin(selected_teams)].copy() if selected_teams else df_cross.copy()

        col1, col2 = st.columns(2)
        with col1:
            if 'クロス総数' in df_cross_f.columns and 'クロス成功数' in df_cross_f.columns:
                df_cross_f['成功率_calc'] = df_cross_f['クロス成功数'] / df_cross_f['クロス総数'].replace(0, np.nan)
                fig = px.scatter(
                    df_cross_f, x='クロス総数', y='成功率_calc',
                    text='チーム名', color='クロス総数',
                    color_continuous_scale='Blues',
                    title='クロス数 vs 成功率',
                    height=450
                )
                fig.update_traces(textposition='top center')
                fig.update_yaxes(tickformat='.1%')
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            right_col = [c for c in df_cross_f.columns if '右' in c and 'クロス' in c and '成功' not in c]
            left_col  = [c for c in df_cross_f.columns if '左' in c and 'クロス' in c and '成功' not in c]
            if right_col and left_col:
                side_data = df_cross_f[['チーム名', right_col[0], left_col[0]]].melt(id_vars='チーム名', var_name='サイド', value_name='クロス数')
                fig2 = px.bar(side_data, x='チーム名', y='クロス数', color='サイド',
                              barmode='group', title='左右サイドクロス比較', height=450)
                fig2.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig2, use_container_width=True)

        fig3 = px.bar(
            df_cross_f.sort_values('クロス総数', ascending=True),
            x='クロス総数', y='チーム名', orientation='h',
            color='クロス総数', color_continuous_scale='Oranges',
            title='クロス総数ランキング',
            height=max(400, len(df_cross_f)*22)
        )
        st.plotly_chart(fig3, use_container_width=True)

        st.markdown("### 📋 クロスデータ一覧")
        st.dataframe(df_cross_f.sort_values('クロス総数', ascending=False).reset_index(drop=True), use_container_width=True)

# ===== タブ10: 守備分析 =====
with tab10:
    st.markdown("## 🛡️ 守備詳細分析")

    df_def = extra.get('def_df', pd.DataFrame())
    if df_def.empty:
        st.warning("守備データが見つかりません。")
    else:
        df_def_f = df_def[df_def['チーム名'].isin(selected_teams)].copy() if selected_teams else df_def.copy()

        col1, col2 = st.columns(2)
        with col1:
            if 'タックル総数' in df_def_f.columns:
                fig = px.bar(
                    df_def_f.sort_values('タックル総数', ascending=True),
                    x='タックル総数', y='チーム名', orientation='h',
                    color='タックル総数', color_continuous_scale='Blues',
                    title='タックル総数ランキング',
                    height=max(400, len(df_def_f)*22)
                )
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            if 'タックル総数' in df_def_f.columns and 'タックル奪取数' in df_def_f.columns:
                df_def_f['奪取率_calc'] = df_def_f['タックル奪取数'] / df_def_f['タックル総数'].replace(0, np.nan)
                fig2 = px.scatter(
                    df_def_f, x='タックル総数', y='奪取率_calc',
                    text='チーム名', color='奪取率_calc',
                    color_continuous_scale='RdYlGn',
                    title='タックル数 vs 奪取率',
                    height=420
                )
                fig2.update_traces(textposition='top center')
                fig2.update_yaxes(tickformat='.1%')
                st.plotly_chart(fig2, use_container_width=True)

        dt_t = [c for c in df_def_f.columns if 'DT' in c and 'タックル' in c]
        mt_t = [c for c in df_def_f.columns if 'MT' in c and 'タックル' in c]
        at_t = [c for c in df_def_f.columns if 'AT' in c and 'タックル' in c]
        if dt_t and mt_t and at_t:
            st.markdown("### エリア別タックル内訳")
            area_df = df_def_f[['チーム名', dt_t[0], mt_t[0], at_t[0]]].copy()
            area_df.columns = ['チーム名', 'DT（守備）', 'MT（中盤）', 'AT（攻撃）']
            area_data = area_df.melt(id_vars='チーム名', var_name='エリア', value_name='タックル数')
            fig3 = px.bar(area_data, x='チーム名', y='タックル数', color='エリア',
                          barmode='stack', title='エリア別タックル数', height=420)
            fig3.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig3, use_container_width=True)

        col1, col2 = st.columns(2)
        clear_col = next((c for c in df_def_f.columns if 'クリア' in c and 'PA' not in c), None)
        inter_col = next((c for c in df_def_f.columns if 'インターセプト' in c), None)

        with col1:
            if clear_col:
                fig4 = px.bar(
                    df_def_f.sort_values(clear_col, ascending=True),
                    x=clear_col, y='チーム名', orientation='h',
                    color=clear_col, color_continuous_scale='Greens',
                    title='クリア数ランキング',
                    height=max(400, len(df_def_f)*22)
                )
                st.plotly_chart(fig4, use_container_width=True)

        with col2:
            if inter_col:
                fig5 = px.bar(
                    df_def_f.sort_values(inter_col, ascending=True),
                    x=inter_col, y='チーム名', orientation='h',
                    color=inter_col, color_continuous_scale='Purples',
                    title='インターセプト数ランキング',
                    height=max(400, len(df_def_f)*22)
                )
                st.plotly_chart(fig5, use_container_width=True)

        radar_candidates = ['タックル総数','クリア','インターセプト','ブロック（シュート）','こぼれ球奪取']
        radar_metrics = [c for c in radar_candidates if c in df_def_f.columns]
        if len(radar_metrics) >= 3:
            st.markdown("### 守備レーダーチャート")
            top5 = df_def_f.nlargest(min(5, len(df_def_f)), radar_metrics[0]).copy()
            for m in radar_metrics:
                mn, mx = df_def_f[m].min(), df_def_f[m].max()
                top5[f'{m}_n'] = ((top5[m] - mn) / (mx - mn + 1e-9) * 100).fillna(0)
            fig6 = go.Figure()
            colors = px.colors.qualitative.Set2
            for i, (_, row) in enumerate(top5.iterrows()):
                vals = [float(row[f'{m}_n']) for m in radar_metrics]
                vals += vals[:1]
                fig6.add_trace(go.Scatterpolar(
                    r=vals, theta=radar_metrics + radar_metrics[:1],
                    fill='toself', name=row['チーム名'],
                    line_color=colors[i % len(colors)], opacity=0.7
                ))
            fig6.update_layout(
                title='守備指標レーダーチャート',
                polar=dict(radialaxis=dict(visible=True, range=[0,100])),
                height=450
            )
            st.plotly_chart(fig6, use_container_width=True)

        st.markdown("### 📋 守備データ一覧")
        sort_col = df_def_f.columns[1] if len(df_def_f.columns) > 1 else 'チーム名'
        st.dataframe(df_def_f.sort_values(sort_col, ascending=False).reset_index(drop=True), use_container_width=True)

    # ===== PPDA =====
    st.markdown("---")
    st.markdown("### 🔥 PPDA（プレッシング強度）")
    st.caption("PPDA = 相手の自陣+中盤パス数 ÷ 自チームの守備アクション（AT+MTタックル奪取 + インターセプト + ファウル）　**数値が小さいほどハイプレスが効いている**")

    df_ppda = extra.get('ppda', pd.DataFrame())
    if not df_ppda.empty:
        df_ppda_f = df_ppda[df_ppda['チーム名'].isin(selected_teams)].copy() if selected_teams else df_ppda.copy()

        col1, col2 = st.columns(2)
        with col1:
            # PPDAランキング棒グラフ（小さいほど良いので昇順）
            df_ppda_sorted = df_ppda_f.sort_values('PPDA', ascending=False)
            fig_ppda = px.bar(
                df_ppda_sorted,
                x='PPDA', y='チーム名', orientation='h',
                color='PPDA',
                color_continuous_scale='RdYlGn_r',  # 小さい=緑、大きい=赤
                title='PPDAランキング（左ほどハイプレス）',
                height=max(400, len(df_ppda_f) * 22)
            )
            fig_ppda.add_vline(x=df_ppda_f['PPDA'].mean(), line_dash='dash',
                               line_color='white', opacity=0.7,
                               annotation_text=f"平均: {df_ppda_f['PPDA'].mean():.1f}",
                               annotation_font_color='white')
            st.plotly_chart(fig_ppda, use_container_width=True)

        with col2:
            # 相手パス数 vs 守備アクション 散布図
            fig_ppda2 = px.scatter(
                df_ppda_f,
                x='守備アクション', y='相手パス合計',
                text='チーム名',
                color='PPDA',
                color_continuous_scale='RdYlGn_r',
                size='守備アクション',
                title='守備アクション数 vs 相手パス数（左下=ハイプレス成功）',
                labels={'守備アクション': '守備アクション数', '相手パス合計': '相手パス数（DT+MT）'},
                height=max(400, len(df_ppda_f) * 22)
            )
            fig_ppda2.update_traces(textposition='top center')
            st.plotly_chart(fig_ppda2, use_container_width=True)

        # PPDAデータテーブル
        st.dataframe(
            df_ppda_f.sort_values('PPDA')[['チーム名','PPDA','相手パス合計','守備アクション']].reset_index(drop=True),
            use_container_width=True
        )

    # ===== 被チャンスクリエイト =====
    st.markdown("---")
    st.markdown("### 🚨 被チャンスクリエイト分析")
    st.caption("被チャンスクリエイト = 相手チームの（スルーパス成功数 + クロス成功数 + ラストパス）の合計　**数値が小さいほど守備的に優れている**")

    df_cc = extra.get('cc', pd.DataFrame())
    if not df_cc.empty:
        df_cc_f = df_cc[df_cc['チーム名'].isin(selected_teams)].copy() if selected_teams else df_cc.copy()

        col1, col2 = st.columns(2)
        with col1:
            # 被CC vs CC 散布図
            fig_cc1 = px.scatter(
                df_cc_f, x='チャンスクリエイト', y='被チャンスクリエイト',
                text='チーム名',
                color='CC差', color_continuous_scale='RdYlGn',
                size='チャンスクリエイト',
                title='チャンスクリエイト vs 被チャンスクリエイト\n（右下＝攻撃力高・守備力高）',
                labels={'チャンスクリエイト':'チャンスクリエイト（攻撃）',
                        '被チャンスクリエイト':'被チャンスクリエイト（守備）'},
                height=450
            )
            fig_cc1.update_traces(textposition='top center')
            # 対角線（攻守均衡ライン）
            mv = max(df_cc_f['チャンスクリエイト'].max(), df_cc_f['被チャンスクリエイト'].max())
            fig_cc1.add_shape(type='line', x0=0, y0=0, x1=mv, y1=mv,
                              line=dict(dash='dash', color='gray'))
            st.plotly_chart(fig_cc1, use_container_width=True)

        with col2:
            # CC差バーチャート
            df_cc_sorted = df_cc_f.sort_values('CC差', ascending=True)
            df_cc_sorted['色'] = df_cc_sorted['CC差'].apply(lambda x: 'プラス（攻撃優位）' if x >= 0 else 'マイナス（守備優位）')
            fig_cc2 = px.bar(
                df_cc_sorted, x='CC差', y='チーム名', orientation='h',
                color='色',
                color_discrete_map={'プラス（攻撃優位）':'#2ecc71','マイナス（守備優位）':'#3498db'},
                title='CC差（CC - 被CC）\nプラス＝相手より多くチャンスを作っている',
                height=450
            )
            fig_cc2.add_vline(x=0, line_color='white', line_width=1)
            st.plotly_chart(fig_cc2, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            # 被CCランキング（少ないほど良い）
            fig_cc3 = px.bar(
                df_cc_f.sort_values('被チャンスクリエイト', ascending=True),
                x='被チャンスクリエイト', y='チーム名', orientation='h',
                color='被チャンスクリエイト', color_continuous_scale='RdYlGn_r',
                title='被チャンスクリエイトランキング（左ほど守備良）',
                height=max(400, len(df_cc_f)*22)
            )
            avg = df_cc_f['被チャンスクリエイト'].mean()
            fig_cc3.add_vline(x=avg, line_dash='dash', line_color='white', opacity=0.7,
                              annotation_text=f"平均:{avg:.0f}", annotation_font_color='white')
            st.plotly_chart(fig_cc3, use_container_width=True)

        with col2:
            # 1試合平均CC vs 被CC
            fig_cc4 = px.scatter(
                df_cc_f, x='CC/試合', y='被CC/試合',
                text='チーム名', color='CC差',
                color_continuous_scale='RdYlGn',
                title='1試合平均 CC vs 被CC\n（右下＝理想）',
                labels={'CC/試合':'CC/試合（攻撃）','被CC/試合':'被CC/試合（守備）'},
                height=max(400, len(df_cc_f)*22)
            )
            fig_cc4.update_traces(textposition='top center')
            st.plotly_chart(fig_cc4, use_container_width=True)

        # データテーブル
        st.dataframe(
            df_cc_f[['チーム名','チャンスクリエイト','被チャンスクリエイト','CC差','CC/試合','被CC/試合']]
            .sort_values('CC差', ascending=False).reset_index(drop=True),
            use_container_width=True
        )

# フッター
st.markdown('---')
st.caption('J2/J3 2026シーズン イベントデータ分析ツール | Powered by Streamlit & Plotly')

# ===== タブ11: APT（ボール保持） =====
with tab11:
    st.markdown("## ⏱️ APT（ボール保持）分析")
    st.caption("APT = Average Possession Time（平均保持時間）")

    if not apt_sheet_data:
        st.warning("APTデータが見つかりません。APTシートを含むXLSXをアップロードしてください。")
    else:
        groups = list(apt_sheet_data.keys())
        sel_groups = st.multiselect("グループを選択", groups, default=groups)

        # 選択グループのデータを結合
        df_apt_all = pd.concat(
            [apt_sheet_data[g].assign(グループ=g) for g in sel_groups if g in apt_sheet_data],
            ignore_index=True
        )

        if df_apt_all.empty:
            st.warning("データがありません")
        else:
            st.markdown("---")

            # グループ別テーブル表示
            for grp in sel_groups:
                if grp not in apt_sheet_data: continue
                df_g = apt_sheet_data[grp].copy()
                st.markdown(f"### {grp}")

                # 基本指標テーブル
                basic_cols = ['チーム名','ボール保持率','保持率順位','APT（分:秒）','APT順位',
                              'ボール保持時間','相手陣保持割合','相手陣保持割合順位','相手陣保持時間']
                st.dataframe(
                    df_g[basic_cols].sort_values('保持率順位').reset_index(drop=True),
                    use_container_width=True, hide_index=True
                )

                # 保持率が多かった試合TOP5
                with st.expander(f"{grp} — 保持率が高かった試合 TOP5"):
                    top5_cols = ['チーム名','保持率1位試合','保持率2位試合','保持率3位試合','保持率4位試合','保持率5位試合']
                    st.dataframe(
                        df_g[top5_cols].sort_values('チーム名').reset_index(drop=True),
                        use_container_width=True, hide_index=True
                    )

            st.markdown("---")
            st.markdown("### 📊 グループ横断グラフ")

            col1, col2 = st.columns(2)
            with col1:
                # 保持率棒グラフ（グループ色分け）
                import plotly.express as px
                # 保持率を数値に戻す
                df_plot = df_apt_all.copy()
                df_plot['保持率_num'] = df_plot['ボール保持率'].str.replace('%','').astype(float)
                fig = px.bar(
                    df_plot.sort_values('保持率_num', ascending=True),
                    x='保持率_num', y='チーム名', color='グループ',
                    orientation='h', title='ボール保持率（降順）',
                    labels={'保持率_num': 'ボール保持率(%)'},
                    height=max(400, len(df_plot)*22)
                )
                fig.add_vline(x=50, line_dash='dash', line_color='white', opacity=0.5)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # 相手陣保持割合棒グラフ
                df_plot['相手陣_num'] = df_plot['相手陣保持割合'].str.replace('%','').astype(float)
                fig2 = px.bar(
                    df_plot.sort_values('相手陣_num', ascending=True),
                    x='相手陣_num', y='チーム名', color='グループ',
                    orientation='h', title='相手陣保持割合（降順）',
                    labels={'相手陣_num': '相手陣保持割合(%)'},
                    height=max(400, len(df_plot)*22)
                )
                st.plotly_chart(fig2, use_container_width=True)

            # 保持率 vs 相手陣保持割合 散布図
            fig3 = px.scatter(
                df_plot, x='保持率_num', y='相手陣_num',
                text='チーム名', color='グループ',
                title='ボール保持率 vs 相手陣保持割合（右上＝主導権を握り前線でも保持）',
                labels={'保持率_num':'ボール保持率(%)','相手陣_num':'相手陣保持割合(%)'},
                height=500
            )
            fig3.update_traces(textposition='top center')
            st.plotly_chart(fig3, use_container_width=True)

# ===== タブ12: チーム詳細レポート =====
with tab12:
    st.markdown("## 📋 チーム詳細レポート")

    # チーム選択
    report_team = st.selectbox("分析するチームを選択", sorted(df_team['チーム名'].dropna().unique()))

    df_report = df_team[
        (df_team['チーム名'] == report_team) &
        (df_team['節'] >= selected_rounds[0]) &
        (df_team['節'] <= selected_rounds[1])
    ].copy()
    df_report_player = df_player[df_player['チーム名'] == report_team].copy()

    if df_report.empty:
        st.warning("該当データがありません")
        st.stop()

    # ===== KPIサマリー =====
    st.markdown(f"### 🏟️ {report_team} — 第{selected_rounds[0]}節〜第{selected_rounds[1]}節")
    n_games = len(df_report)
    wins   = len(df_report[df_report['得点'] > df_report['失点']])
    draws  = len(df_report[df_report['得点'] == df_report['失点']])
    losses = len(df_report[df_report['得点'] < df_report['失点']])

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("試合数", n_games)
    c2.metric("勝", wins)
    c3.metric("分", draws)
    c4.metric("負", losses)
    c5.metric("得点", int(df_report['得点'].sum()))
    c6.metric("失点", int(df_report['失点'].sum()))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("xG", f"{df_report['xG'].sum():.2f}")
    c2.metric("シュート", int(df_report['シュート'].sum()))
    c3.metric("パス成功率", f"{(df_report['パス成功数'].sum() / df_report['パス総数'].sum() * 100):.1f}%")
    c4.metric("ボール保持率", f"{(df_report['ボール保持率'].mean() * 100):.1f}%")

    # ===== APTデータ =====
    if apt_sheet_data:
        st.markdown("---")
        st.markdown("### ⏱️ ボール保持データ（APT）")

        # 対象チームのグループを特定
        team_group = None
        for grp, df_grp in apt_sheet_data.items():
            if report_team in df_grp['チーム名'].values:
                team_group = grp
                break

        if team_group:
            df_apt_grp = apt_sheet_data[team_group].copy()
            df_apt_team = df_apt_grp[df_apt_grp['チーム名'] == report_team]

            if not df_apt_team.empty:
                r = df_apt_team.iloc[0]
                ca1, ca2, ca3, ca4 = st.columns(4)
                ca1.metric("ボール保持率", r['ボール保持率'], f"グループ{r['保持率順位']}位")
                ca2.metric("APT（平均保持時間）", r['APT（分:秒）'], f"グループ{r['APT順位']}位")
                ca3.metric("ボール保持時間", r['ボール保持時間'])
                ca4.metric("相手陣保持割合", r['相手陣保持割合'], f"グループ{r['相手陣保持割合順位']}位")

            st.markdown(f"#### {team_group} グループ APT一覧")

            # 対象チームをハイライト
            def highlight_team(row):
                color = 'background-color: rgba(255,100,100,0.3)' if row['チーム名'] == report_team else ''
                return [color] * len(row)

            st.dataframe(
                df_apt_grp.sort_values('保持率順位').reset_index(drop=True)
                .style.apply(highlight_team, axis=1),
                use_container_width=True
            )

    st.markdown("---")

    # ===== 他チームとの比較（レーダーチャート） =====
    st.markdown("### 📡 他チームとの比較")

    # 全チーム集計（リーグ全体）
    all_team_agg = df_team[
        (df_team['節'] >= selected_rounds[0]) &
        (df_team['節'] <= selected_rounds[1])
    ].groupby('チーム名').agg(
        得点=('得点','sum'), 失点=('失点','sum'),
        シュート=('シュート','sum'), 枠内シュート=('枠内シュート','sum'),
        xG=('xG','sum'), パス総数=('パス総数','sum'), パス成功数=('パス成功数','sum'),
        ドリブル成功数=('ドリブル成功数','sum'), タックル奪取数=('タックル奪取数','sum'),
        インターセプト=('インターセプト','sum'), ボール保持率=('ボール保持率','mean'),
        クロス成功数=('クロス成功数','sum'),
    ).reset_index()
    all_team_agg['パス成功率'] = (all_team_agg['パス成功数'] / all_team_agg['パス総数'].replace(0, np.nan) * 100).round(1)
    all_team_agg['枠内率'] = (all_team_agg['枠内シュート'] / all_team_agg['シュート'].replace(0, np.nan) * 100).round(1)
    all_team_agg['保持率(%)'] = (all_team_agg['ボール保持率'] * 100).round(1)

    # 比較チーム選択
    other_teams = [t for t in sorted(df_team['チーム名'].unique()) if t != report_team]
    compare_teams = st.multiselect(
        "比較するチームを選択（最大5チーム）",
        other_teams,
        default=other_teams[:4],
        max_selections=5
    )
    radar_teams = [report_team] + compare_teams

    radar_metrics = ['シュート','枠内率','パス成功率','保持率(%)','ドリブル成功数','タックル奪取数','インターセプト']
    radar_data = all_team_agg[all_team_agg['チーム名'].isin(radar_teams)].copy()
    for m in radar_metrics:
        mn, mx = all_team_agg[m].min(), all_team_agg[m].max()
        radar_data[f'{m}_n'] = ((radar_data[m] - mn) / (mx - mn + 1e-9) * 100).fillna(0)

    col1, col2 = st.columns(2)
    with col1:
        fig_radar = go.Figure()
        colors = ['#FF6B6B'] + list(px.colors.qualitative.Set2)
        for i, team in enumerate(radar_teams):
            row = radar_data[radar_data['チーム名'] == team]
            if row.empty: continue
            vals = [float(row[f'{m}_n'].values[0]) for m in radar_metrics]
            vals += vals[:1]
            lw = 3 if team == report_team else 1.5
            fig_radar.add_trace(go.Scatterpolar(
                r=vals, theta=radar_metrics + radar_metrics[:1],
                fill='toself', name=team,
                line=dict(color=colors[i % len(colors)], width=lw),
                opacity=0.8 if team == report_team else 0.5
            ))
        fig_radar.update_layout(
            title=f'{report_team} vs 他チーム レーダーチャート',
            polar=dict(radialaxis=dict(visible=True, range=[0,100])),
            height=480
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with col2:
        # 主要指標の全体順位
        st.markdown(f"#### {report_team} のリーグ順位")
        rank_metrics = ['得点','失点','xG','シュート','パス成功率','保持率(%)','ドリブル成功数','タックル奪取数','インターセプト']
        rank_rows = []
        for m in rank_metrics:
            ascending = (m == '失点')  # 失点は少ないほど良い
            ranked = all_team_agg.sort_values(m, ascending=ascending).reset_index(drop=True)
            rank = ranked[ranked['チーム名'] == report_team].index[0] + 1 if report_team in ranked['チーム名'].values else '-'
            val = all_team_agg[all_team_agg['チーム名'] == report_team][m].values
            val_str = f"{val[0]:.1f}" if len(val) > 0 else '-'
            total = len(all_team_agg)
            rank_rows.append({'指標': m, '値': val_str, f'順位（/{total}）': rank})
        st.dataframe(pd.DataFrame(rank_rows), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ===== 選手個人スタッツ一覧 =====
    st.markdown("### 👥 選手個人スタッツ一覧")

    # 選手集計
    p_agg = df_report_player.groupby(['選手名','ポジション']).agg(
        出場時間=('出場時間','sum'),
        試合数=('節','count'),
        ゴール=('ゴール','sum'),
        アシスト=('アシスト','sum'),
        シュート=('シュート','sum'),
        枠内シュート=('枠内シュート','sum'),
        ラストパス=('ラストパス','sum'),
        パス総数=('パス総数','sum'),
        パス成功数=('パス成功数','sum'),
        スルーパス成功数=('スルーパス成功数','sum'),
        クロス成功数=('クロス成功数','sum'),
        ドリブル成功数=('ドリブル成功数','sum'),
        タックル奪取数=('タックル奪取数','sum'),
        インターセプト=('インターセプト','sum'),
        空中戦勝ち数=('空中戦勝ち数','sum'),
        クリア=('クリア','sum'),
        セーブ=('セーブ','sum'),
        スプリント回数=('スプリント回数','sum'),
    ).reset_index()

    p_agg['パス成功率'] = (p_agg['パス成功数'] / p_agg['パス総数'].replace(0, np.nan) * 100).round(1)
    p_agg['枠内率'] = (p_agg['枠内シュート'] / p_agg['シュート'].replace(0, np.nan) * 100).round(1)
    p_agg['チャンスクリエイト'] = p_agg['スルーパス成功数'] + p_agg['クロス成功数'] + p_agg['ラストパス']
    p_agg['90分換算ゴール'] = (p_agg['ゴール'] / p_agg['出場時間'].replace(0, np.nan) * 90).round(2)
    p_agg['90分換算CC'] = (p_agg['チャンスクリエイト'] / p_agg['出場時間'].replace(0, np.nan) * 90).round(2)

    # マスター結合（あれば）
    if player_master is not None:
        pm = player_master[['選手名','背番号','年齢','身長']].drop_duplicates('選手名')
        p_agg = p_agg.merge(pm, on='選手名', how='left')

    # ポジション別タブ
    for tab_p, pos in zip(st.tabs(['全員','GK','DF','MF','FW']), ['全員','GK','DF','MF','FW']):
        with tab_p:
            df_pos = p_agg if pos == '全員' else p_agg[p_agg['ポジション'] == pos]

            base_cols = ['選手名','ポジション']
            if player_master is not None:
                base_cols += [c for c in ['背番号','年齢','身長'] if c in df_pos.columns]
            base_cols += ['試合数','出場時間','ゴール','アシスト','チャンスクリエイト','90分換算ゴール','90分換算CC']

            extra_cols = {
                'GK': ['セーブ','クリア','パス成功率'],
                'DF': ['タックル奪取数','インターセプト','クリア','空中戦勝ち数','パス成功率'],
                'MF': ['パス成功率','ドリブル成功数','スルーパス成功数','クロス成功数','スプリント回数'],
                'FW': ['シュート','枠内率','枠内シュート','ドリブル成功数'],
            }
            if pos in extra_cols:
                show_cols = base_cols + [c for c in extra_cols[pos] if c in df_pos.columns]
            else:
                show_cols = base_cols

            show_cols = [c for c in show_cols if c in df_pos.columns]
            st.dataframe(
                df_pos[show_cols].sort_values('出場時間', ascending=False).reset_index(drop=True),
                use_container_width=True
            )
