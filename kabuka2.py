import pandas as pd
import yfinance as yf
import altair as alt
import streamlit as st
import traceback
from datetime import datetime, timedelta # timedelta をインポート

st.title("米国株価可視化アプリ")

st.sidebar.write("""
# 米国主要テック株価
こちらは株価可視化ツールです。以下のオプションから表示日数やチャートの種類を指定してください。
""")

st.sidebar.write("""
## 表示日数選択
""")
# スライダーのデフォルト値を調整 (例: 30日)
days = st.sidebar.slider("日数", 1, 100, 30) # 最大日数を増やし、デフォルトを変更

st.sidebar.write("""
## 株価の範囲指定
""")
# スライダーのデフォルト値を調整 (データに合わせて変更推奨)
ymin, ymax = st.sidebar.slider(
    "範囲を指定してください。",
    0.0, 550.0, (0.0, 550.0) # Meta, Netflix等の株価に合わせて上限を調整
)

# --- データ取得関数 (OHLCデータを取得するように変更) ---
@st.cache_data
def get_data(days, tickers):
    """指定された日数とティッカーリストに基づいてOHLCデータを取得する"""
    try:
        # yf.downloadは過去N日分を取得するため、期間を指定
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1) # days=1なら今日のみ

        # 全ティッカーのデータを一度に取得
        tkr_list = list(tickers.values())
        hist = yf.download(tkr_list, start=start_date, end=end_date)

        # データが取得できなかった場合のチェック
        if hist.empty:
            st.error("指定された期間の株価データを取得できませんでした。")
            return None
        # データが1日分しかない場合のインデックス調整
        if len(tkr_list) == 1 and isinstance(hist.index, pd.DatetimeIndex) == False:
             # 1銘柄だけだとMultiIndexにならない場合があるため調整
             if not isinstance(hist.columns, pd.MultiIndex):
                 hist = pd.concat({tkr_list[0]: hist}, axis=1)
                 hist.columns = pd.MultiIndex.from_tuples([(col, tkr) for col, tkr in zip(hist.columns, [tkr_list[0]]*len(hist.columns))])


        # カラム名からティッカーを会社名にマッピングする辞書を作成
        ticker_to_name = {v: k for k, v in tickers.items()}

        # 'Close' データのみを抽出して整形 (複数ラインチャート用)
        df_close = hist["Close"].copy()
        # 日付のフォーマットを適用（ただしAltairはDatetimeオブジェクトを好む）
        # df_close.index = df_close.index.strftime("%d %B %Y") # Altairのためにコメントアウト推奨
        df_close.columns = df_close.columns.map(ticker_to_name) # 列名を会社名に
        df_close = df_close.T # 会社を行、日付を列に転置
        df_close.index.name = "Name"

        return hist, df_close # 元のOHLCデータと整形済みCloseデータを返す

    except Exception as e:
        st.error(f"データ取得中にエラーが発生しました: {e}")
        st.error(traceback.format_exc())
        return None, None

# --- メイン処理 ---
try:
    tickers = {
        "apple": "AAPL",
        "meta": "META",
        "google": "GOOGL",
        "microsoft": "MSFT",
        "netflix": "NFLX",
        "amazon": "AMZN"
    }
    company_names = list(tickers.keys())

    # --- データ取得 ---
    hist_data, df_close_processed = get_data(days, tickers)

    if hist_data is not None and df_close_processed is not None:

        # --- チャート種類選択 ---
        chart_type = st.radio(
            "表示するチャートの種類を選択",
            ('複数ラインチャート', 'ローソク足チャート')
        )

        st.write(f"""### 過去 **{days}日間** の株価""")

        # --- 複数ラインチャート ---
        if chart_type == '複数ラインチャート':
            st.sidebar.write("---") # 区切り線
            st.sidebar.write("## 表示する会社を選択")
            companies = st.sidebar.multiselect(
                "会社名を選択してください。（複数選択可）",
                company_names,
                ["google", "amazon", "meta", "apple"] # デフォルト選択
            )

            if not companies:
                st.error("少なくとも一社は選んでください。")
            else:
                # 選択された会社のデータのみをフィルタリング
                data_lines = df_close_processed.loc[companies]
                st.write("### 株価（USD） - 終値ベース", data_lines.sort_index())

                # Altair用にデータを整形 (Melt)
                data_melt = data_lines.T.reset_index()
                # 'Date' 列が DatetimeIndex から変換された場合の列名を確認（通常は 'Date' or 'index'）
                date_col_name = data_melt.columns[0] # 最初の列を日付列と仮定
                data_melt = pd.melt(data_melt, id_vars=[date_col_name]).rename(
                    columns={date_col_name: "Date", "value": "Stock Prices(USD)"}
                )

                # ラインチャート作成
                chart_line = (
                    alt.Chart(data_melt)
                    .mark_line(opacity=0.8, clip=True)
                    .encode(
                        x="Date:T", # 時間軸として扱う
                        y=alt.Y("Stock Prices(USD):Q", stack=None, scale=alt.Scale(domain=[ymin, ymax])),
                        color="Name:N",
                        tooltip=['Date', 'Name', 'Stock Prices(USD)'] # ツールチップ追加
                    )
                    .interactive() # ズームやパンを可能にする
                )
                st.altair_chart(chart_line, use_container_width=True)

        # --- ローソク足チャート ---
        elif chart_type == 'ローソク足チャート':
            st.sidebar.write("---") # 区切り線
            st.sidebar.write("## 表示する会社を選択")
            selected_company = st.sidebar.selectbox(
                "会社名を選択してください。",
                company_names,
                index=company_names.index("apple") # デフォルトでappleを選択
            )

            selected_ticker = tickers[selected_company]
            st.write(f"### {selected_company} ({selected_ticker}) のローソク足チャート")

            # 選択された会社のOHLCデータを抽出
            # MultiIndexから特定のティッカーのデータを抽出
            ohlc_data = hist_data.loc[:, (slice(None), selected_ticker)]
            ohlc_data.columns = ohlc_data.columns.droplevel(1) # 上位レベルのインデックス（ティッカー名）を削除
            ohlc_data = ohlc_data[['Open', 'High', 'Low', 'Close']].reset_index() # 必要な列を選択し、Dateを列にする

            if ohlc_data.empty:
                st.error(f"{selected_company} のOHLCデータを取得できませんでした。")
            else:
                # ローソク足チャート作成
                base = alt.Chart(ohlc_data).encode(
                    x='Date:T',
                    color=alt.condition("datum.Open <= datum.Close", alt.value("#06982d"), alt.value("#ae1325")), # 陽線は緑、陰線は赤
                    tooltip=[
                        alt.Tooltip('Date', title='日付'),
                        alt.Tooltip('Open', title='始値', format='.2f'),
                        alt.Tooltip('High', title='高値', format='.2f'),
                        alt.Tooltip('Low', title='安値', format='.2f'),
                        alt.Tooltip('Close', title='終値', format='.2f')
                    ]
                )

                # 高値-安値の線（ヒゲ）
                rule = base.mark_rule().encode(
                    y=alt.Y('Low:Q', title='Price (USD)', scale=alt.Scale(domain=[ymin, ymax])),
                    y2='High:Q'
                )

                # 始値-終値のバー（実体）
                bar = base.mark_bar().encode(
                    y='Open:Q',
                    y2='Close:Q'
                )

                chart_candle = (rule + bar).interactive() # ズームやパンを可能にする

                st.altair_chart(chart_candle, use_container_width=True)

    else:
        st.error("データの取得または処理に失敗しました。")

except Exception as e:
    st.error(f"アプリケーションで予期せぬエラーが発生しました: {e}")
    st.error(traceback.format_exc())