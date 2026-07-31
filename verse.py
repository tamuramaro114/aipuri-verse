import base64
import io
import os
import cv2
from google.oauth2.service_account import Credentials
import gspread
import numpy as np
import pandas as pd
from PIL import Image, ImageOps
import qrcode
import streamlit as st

# --- Googleスプレッドシート & 認証の設定 ---
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


@st.cache_resource
def init_gspread():
  try:
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    if "sheet_name" in st.secrets.get("gcp_service_account", {}):
      target = st.secrets["gcp_service_account"]["sheet_name"]
    else:
      target = st.secrets.get("sheet_name", "aipri_database")

    if len(target) > 30 and "/" not in target:
      sheet = client.open_by_key(target).sheet1
    else:
      sheet = client.open(target).sheet1

    return sheet
  except Exception as e:
    st.error(
        f"Googleスプレッドシートへの接続に失敗しました。Secretsの設定や共有設定を確認してください: {e}"
    )
    return None


def load_data():
  sheet = init_gspread()
  if sheet is None:
    return pd.DataFrame(columns=[
        "id",
        "code_name",
        "bullet",
        "attribute",
        "part",
        "character",
        "image_base64",
    ])

  try:
    data = sheet.get_all_records()
    df = pd.DataFrame(data)

    expected_cols = [
        "id",
        "code_name",
        "bullet",
        "attribute",
        "part",
        "character",
        "image_base64",
    ]
    if df.empty:
      return pd.DataFrame(columns=expected_cols)

    for col in expected_cols:
      if col not in df.columns:
        df[col] = ""

    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df["image_base64"] = df["image_base64"].fillna("").astype(str)
    return df
  except Exception as e:
    st.error(f"データの読み込みエラー: {e}")
    return pd.DataFrame(columns=[
        "id",
        "code_name",
        "bullet",
        "attribute",
        "part",
        "character",
        "image_base64",
    ])


def save_data(df):
  sheet = init_gspread()
  if sheet is None:
    st.error("スプレッドシートに接続できないため保存できません。")
    return

  try:
    sheet.clear()
    df_to_save = df.fillna("")
    data_to_write = [df_to_save.columns.tolist()] + df_to_save.values.tolist()
    sheet.update(data_to_write)
  except Exception as e:
    st.error(f"Googleスプレッドシートへの保存に失敗しました: {e}")


def process_and_optimize_qr(uploaded_image):
  try:
    image = Image.open(uploaded_image)
    image = ImageOps.exif_transpose(image)

    if image.mode in ("RGBA", "P"):
      image = image.convert("RGB")

    img_np = np.array(image)
    if len(img_np.shape) == 3 and img_np.shape[2] == 3:
      img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
      img_cv = img_np

    detector = cv2.QRCodeDetector()
    data, bbox, rectified_image = detector.detectAndDecode(img_cv)

    if data and rectified_image is not None and rectified_image.size > 0:
      if len(rectified_image.shape) == 3:
        rect_gray = cv2.cvtColor(rectified_image, cv2.COLOR_BGR2GRAY)
      else:
        rect_gray = rectified_image

      _, thresh = cv2.threshold(
          rect_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
      )
      qr_pil = Image.fromarray(thresh).convert("1")

      scale_factor = 25
      new_width = qr_pil.width * scale_factor
      new_height = qr_pil.height * scale_factor
      qr_large = qr_pil.resize(
          (new_width, new_height), Image.Resampling.NEAREST
      )

      output = io.BytesIO()
      qr_large.save(output, format="PNG")
      return (
          output.getvalue(),
          "success",
          f"QRコードを高解像度で抽出しました！ (データ: {data[:20]}...)",
      )
    else:
      max_size = 800
      if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

      output = io.BytesIO()
      image.save(output, format="JPEG", quality=85)
      return (
          output.getvalue(),
          "fallback",
          "⚠️ QRコード検出に失敗したため画像を圧縮保存しました。",
      )

  except Exception as e:
    try:
      image = Image.open(uploaded_image)
      image = ImageOps.exif_transpose(image)
      if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
      output = io.BytesIO()
      image.save(output, format="JPEG", quality=85)
      return (
          output.getvalue(),
          "error",
          f"処理中エラーが発生しましたが代替保存しました: {e}",
      )
    except Exception as e2:
      return (
          b"",
          "error",
          f"画像の読み込みに完全に失敗しました。ファイル形式を確認してください: {e2}",
      )


data = load_data()

st.title("✨ アイプリバース プリフォト管理アプリ ✨")
st.sidebar.header("メニュー")
menu = st.sidebar.radio(
    "選択してください",
    [
        "コレクション一覧・検索",
        "プリフォトを追加する",
        "🎯 弾別コンプリート状況",
        "🎯 チャンスコード集",
    ],
)

st.sidebar.markdown("---")
st.sidebar.subheader("💾 データ管理")

if not data.empty:
  csv_data = data.to_csv(index=False).encode("utf-8")
  st.sidebar.download_button(
      label="📥 CSVをダウンロード",
      data=csv_data,
      file_name="aipri_data_backup.csv",
      mime="text/csv",
  )

st.sidebar.markdown("---")

NORMAL_BULLET_OPTIONS = []
for i in range(1, 7):
  NORMAL_BULLET_OPTIONS.append(f"{i}だん")
for i in range(1, 7):
  NORMAL_BULLET_OPTIONS.append(f"リング{i}だん")
for i in range(1, 7):
  NORMAL_BULLET_OPTIONS.append(f"おねがい{i}だん")

MILLEFEE_BULLET_OPTIONS = [
    "vol.1",
    "vol.2",
    "vol.3",
    "Rvol.1",
    "Rvol.2",
    "Rvol.3",
    "おねがいvol.1",
    "おねがいvol.2",
]
GUMMI_BULLET_OPTIONS = ["グミvol.1", "グミvol.2", "グミvol.3"]
ALL_BULLET_OPTIONS = (
    NORMAL_BULLET_OPTIONS + MILLEFEE_BULLET_OPTIONS + GUMMI_BULLET_OPTIONS
)

ATTRIBUTE_OPTIONS = [
    "つうじょう",
    "プリティー",
    "特殊",
    "シークレット",
    "チャンスコーデ",
    "コラボ",
    "フルコーデ",
    "ミルフィー",
    "グミ",
    "ひろば",
    "チャンス本体",
]

PART_OPTIONS = [
    "アクセ",
    "ワンピース",
    "トップス",
    "ボトムス",
    "シューズ",
    "フルコーデ",
]


def get_attr_list(attr_str):
  if not isinstance(attr_str, str) or not attr_str.strip():
    return []
  raw_list = (
      attr_str.replace("、", ",")
      .replace("/", ",")
      .replace(" ", "")
      .split(",")
  )
  return [a.strip() for a in raw_list if a.strip()]


# ---------------------------------------------------------
# 1. コレクション一覧・検索画面
# ---------------------------------------------------------
if menu == "コレクション一覧・検索":
  st.header("📖 マイ・プリフォトコレクション")

  if data.empty:
    st.info("まだプリフォトが登録されていません。")
  else:
    st.sidebar.markdown("### 🔍 検索・絞り込み・並べ替え")
    search_keyword = st.sidebar.text_input("コーデ名・キャラ名で検索")

    selected_attribute = st.sidebar.selectbox(
        "属性（ジャンル）で絞り込み", ["すべて"] + ATTRIBUTE_OPTIONS
    )

    filter_bullet = st.sidebar.selectbox(
        "弾数で絞り込み", ["すべて"] + list(data["bullet"].unique())
    )

    sort_option = st.sidebar.selectbox(
        "並べ替え", ["登録順 (新しい順)", "登録順 (古い順)", "コーデ名順"]
    )

    cols_per_row = st.sidebar.slider(
        "横に並べるカードの数", min_value=2, max_value=6, value=3
    )

    if cols_per_row <= 3:
      title_font_size = "1.0rem"
      sub_font_size = "0.85rem"
    elif cols_per_row == 4:
      title_font_size = "0.9rem"
      sub_font_size = "0.75rem"
    else:
      title_font_size = "0.8rem"
      sub_font_size = "0.65rem"

    filtered_data = data.copy()

    # 「チャンス本体」を含むQRコードをコレクション一覧に表示させない
    if not filtered_data.empty:
      filtered_data = filtered_data[
          ~filtered_data["attribute"].apply(
              lambda x: "チャンス本体" in get_attr_list(str(x))
          )
      ]

    if search_keyword:
      filtered_data = filtered_data[
          filtered_data["code_name"].str.contains(search_keyword, na=False)
          | filtered_data["character"].str.contains(search_keyword, na=False)
      ]

    if selected_attribute != "すべて":
      filtered_data = filtered_data[
          filtered_data["attribute"].apply(
              lambda x: selected_attribute in get_attr_list(str(x))
          )
      ]

    if filter_bullet != "すべて":
      filtered_data = filtered_data[filtered_data["bullet"] == filter_bullet]

    if sort_option == "登録順 (新しい順)":
      filtered_data = filtered_data.sort_values(by="id", ascending=False)
    elif sort_option == "登録順 (古い順)":
      filtered_data = filtered_data.sort_values(by="id", ascending=True)
    elif sort_option == "コーデ名順":
      filtered_data = filtered_data.sort_values(by="code_name", ascending=True)

    st.write(
        f"全 **{len(data)}** 枚中（チャンス本体除外後） / 表示件数: **{len(filtered_data)}** 枚"
    )

    for idx, (i, row) in enumerate(filtered_data.iterrows()):
      if idx % cols_per_row == 0:
        col = st.columns(cols_per_row)

      with col[idx % cols_per_row]:
        st.markdown(
            f"<p style='font-size: {title_font_size}; font-weight: bold; margin-bottom: 0.2rem;'>{row['code_name']}</p>",
            unsafe_allow_html=True,
        )

        if pd.notna(row["image_base64"]) and row["image_base64"] != "":
          try:
            image_bytes = base64.b64decode(row["image_base64"])
            st.markdown(
                f"""
                        <div style="background-color: #ffffff; padding: 6px; border-radius: 6px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 0.3rem;">
                            <img src="data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}" style="width: 100%; max-width: 320px; height: auto; image-rendering: pixelated; image-rendering: crisp-edges; display: block; margin: 0 auto;">
                        </div>
                        """,
                unsafe_allow_html=True,
            )
          except:
            st.warning("画像エラー")
        else:
          st.info("📷 画像なし")

        char_text = (
            f"👤 {row['character']}"
            if row.get("character", "") != ""
            else "👤 なし"
        )
        attr_text = (
            f"✨ {row['attribute']}"
            if row.get("attribute", "") != ""
            else ""
        )
        st.markdown(
            f"<p style='font-size: {sub_font_size}; color: #555; margin: 0;'>{char_text} / {attr_text}</p>"
            f"<p style='font-size: {sub_font_size}; color: #555; margin-bottom: 0.5rem;'>🏷️ {row['bullet']} /👗 {row.get('part', '')}</p>",
            unsafe_allow_html=True,
        )

        b_col1, b_col2 = st.columns(2)
        with b_col1:
          if st.button("✏️ 編集", key=f"edit_btn_{row['id']}"):
            st.session_state[f"editing_{row['id']}"] = True
        with b_col2:
          if st.button("🗑️ 削除", key=f"del_{row['id']}"):
            data = data[data["id"] != row["id"]]
            save_data(data)
            st.success("削除しました！")
            st.rerun()

        if st.session_state.get(f"editing_{row['id']}", False):
          with st.form(key=f"edit_form_{row['id']}"):
            st.markdown(f"**ID: {row['id']} の編集**")
            new_code_name = st.text_input("コーデ名", value=row["code_name"])

            current_attrs = get_attr_list(row["attribute"])
            valid_default_attrs = [
                a for a in current_attrs if a in ATTRIBUTE_OPTIONS
            ]

            new_attributes = st.multiselect(
                "属性（複数選択可）",
                ATTRIBUTE_OPTIONS,
                default=valid_default_attrs,
            )

            bullet_idx = (
                ALL_BULLET_OPTIONS.index(row["bullet"])
                if row["bullet"] in ALL_BULLET_OPTIONS
                else 0
            )
            part_idx = (
                PART_OPTIONS.index(row.get("part", "アクセ"))
                if row.get("part", "アクセ") in PART_OPTIONS
                else 0
            )

            new_bullet = st.selectbox("弾数", ALL_BULLET_OPTIONS, index=bullet_idx)
            new_part = st.selectbox("部位", PART_OPTIONS, index=part_idx)
            new_character = st.text_input(
                "キャラクター名", value=row.get("character", "")
            )

            col_save, col_cancel = st.columns(2)
            with col_save:
              if st.form_submit_button("保存"):
                combined_attr = (
                    ",".join(new_attributes) if new_attributes else ""
                )
                data.loc[data["id"] == row["id"], "code_name"] = new_code_name
                data.loc[data["id"] == row["id"], "attribute"] = combined_attr
                data.loc[data["id"] == row["id"], "bullet"] = new_bullet
                data.loc[data["id"] == row["id"], "part"] = new_part
                data.loc[data["id"] == row["id"], "character"] = new_character
                save_data(data)
                st.session_state[f"editing_{row['id']}"] = False
                st.success("更新しました！")
                st.rerun()
            with col_cancel:
              if st.form_submit_button("キャンセル"):
                st.session_state[f"editing_{row['id']}"] = False
                st.rerun()

        st.markdown("---")

# ---------------------------------------------------------
# 2. プリフォト追加画面
# ---------------------------------------------------------
elif menu == "プリフォトを追加する":
  st.header("📸 新しいプリフォトの登録")

  if "code_name_input" not in st.session_state:
    st.session_state["code_name_input"] = ""

  uploaded_image = st.file_uploader(
      "プリフォトの画像", type=["jpg", "png", "jpeg"]
  )

  processed_bytes = None
  if uploaded_image is not None:
    file_base_name = os.path.splitext(uploaded_image.name)[0]
    with st.spinner("QRコードを処理中..."):
      processed_bytes, status, msg = process_and_optimize_qr(uploaded_image)
    st.success(msg)

    if processed_bytes:
      encoded_preview = base64.b64encode(processed_bytes).decode("utf-8")
      st.markdown(
          f"""
          <div style="background-color: white; padding: 15px; display: inline-block; border-radius: 8px; border: 1px solid #ddd; text-align: center;">
              <img src="data:image/png;base64,{encoded_preview}" width="350" style="image-rendering: pixelated; image-rendering: crisp-edges;">
          </div>
          """,
          unsafe_allow_html=True,
      )

    if st.button("✨ ファイル名をコーデ名として使う"):
      st.session_state["code_name_input"] = file_base_name
      st.rerun()

  with st.form("add_form", clear_on_submit=True):
    code_name = st.text_input(
        "コーデ名", value=st.session_state["code_name_input"]
    )
    selected_attributes = st.multiselect(
        "属性（複数選択可）", ATTRIBUTE_OPTIONS, default=["つうじょう"]
    )
    bullet = st.radio("弾数", ALL_BULLET_OPTIONS, horizontal=True)
    part = st.radio("部位", PART_OPTIONS, horizontal=True)
    character = st.text_input("キャラクター名")

    if st.form_submit_button("登録する"):
      if not code_name or uploaded_image is None or processed_bytes is None:
        st.error("コーデ名と有効な画像を入力してください。")
      else:
        new_id = (
            int(data["id"].max() + 1)
            if not data.empty and not pd.isna(data["id"].max())
            else 1
        )
        image_base64 = base64.b64encode(processed_bytes).decode("utf-8")
        combined_attr = (
            ",".join(selected_attributes) if selected_attributes else ""
        )
        new_row = pd.DataFrame({
            "id": [new_id],
            "code_name": [code_name],
            "bullet": [bullet],
            "attribute": [combined_attr],
            "part": [part],
            "character": [character],
            "image_base64": [image_base64],
        })
        data = pd.concat([data, new_row], ignore_index=True)
        save_data(data)
        st.success("✨ 登録しました！")

# ---------------------------------------------------------
# 3. 弾別コンプリート状況（外部CSV対応 / 分割・実質％対応）
# ---------------------------------------------------------
elif menu == "🎯 弾別コンプリート状況":
  st.header("🎯 弾別コンプリート状況チェッカー")
  st.write(
      "外部（GitHubなど）に配置した各弾のマスターCSVを読み込み、所持状況をチェックします。"
  )

  bullet_csv_urls = {
      "おねがい1だん": (
          "https://raw.githubusercontent.com/tamuramaro114/aipuri-verse/main/aipri_master/onegai1_master.csv"
      ),
      "おねがい2だん": (
          "https://raw.githubusercontent.com/tamuramaro114/aipuri-verse/main/aipri_master/onegai2_master.csv"
      ),
      "おねがい3だん": (
          "https://raw.githubusercontent.com/tamuramaro114/aipuri-verse/main/aipri_master/onegai3_master.csv"
      ),
      "リング6だん": (
          "https://raw.githubusercontent.com/tamuramaro114/aipuri-verse/main/aipri_master/ring6_master.csv"
      ),
  }

  selected_bullet_target = st.selectbox(
      "確認したい弾を選択してください", list(bullet_csv_urls.keys())
  )

  csv_url = bullet_csv_urls.get(selected_bullet_target)

  if not csv_url or "YOUR_NAME" in csv_url:
    st.warning(
        "⚠️ 選択した弾のCSVファイルのURLが正しく設定されていません。"
        "コード内の `bullet_csv_urls` に正しいGitHub（Raw）のリンクを設定してください。"
    )
  else:
    try:
      master_df = pd.read_csv(
          csv_url, on_bad_lines="skip", encoding="utf-8-sig", skipinitialspace=True
      )
      master_df.columns = master_df.columns.str.strip()
      owned_df = data[data["bullet"] == selected_bullet_target]

      checked_list = []

      # カウント用変数
      normal_total = 0
      normal_owned = 0
      normal_actual = 0  # 所持 + 內定

      chance_total = 0
      chance_owned = 0
      chance_actual = 0  # 所持 + 內定

      for _, row in master_df.iterrows():
        code_name = str(row["code_name"]).strip()
        attribute = str(row.get("attribute", "つうじょう")).strip()
        part = str(row["part"]).strip()

        # 判定：チャンスコーデ系かどうか
        is_chance_item = (
            "チャンスコーデ" in attribute
            or "チャンスコーデ" in master_df.columns
            and row.get("attribute", "") == "チャンスコーデ"
        )

        # 所持判定（コーデ名と部位で判定）
        match = owned_df[
            (owned_df["code_name"] == code_name) & (owned_df["part"] == part)
        ]
        is_owned = not match.empty

        status_str = "❌ 未所持"
        if is_owned:
          status_str = "✅ 所持"
        else:
          # 内定判定（チャンス本体を所持しているか）
          has_chance_body = not owned_df[
              (owned_df["code_name"] == code_name)
              & (
                  owned_df["attribute"].apply(
                      lambda x: "チャンス本体" in get_attr_list(str(x))
                  )
              )
          ].empty

          if is_chance_item and has_chance_body:
            status_str = "🆗内定"

        # 集計への加算
        if is_chance_item:
          chance_total += 1
          if status_str == "✅ 所持":
            chance_owned += 1
            chance_actual += 1
          elif status_str == "🆗内定":
            chance_actual += 1
        else:
          normal_total += 1
          if status_str == "✅ 所持":
            normal_owned += 1
            normal_actual += 1
          elif status_str == "🆗内定":
            normal_actual += 1

        checked_list.append({
            "コーデ名": code_name,
            "属性": attribute,
            "部位": part,
            "状態": status_str,
            "種別": "チャンスコーデ" if is_chance_item else "チャンスコーデ以外",
        })

      check_df = pd.DataFrame(checked_list)

# --- 進捗の表示（2つに分けて表示・文字サイズ調整版） ---
      st.subheader("📊 コンプリート進捗状況")

      col_n, col_c = st.columns(2)

      with col_n:
        st.markdown("### 🏷️ チャンスコーデ以外")
        n_rate = normal_owned / normal_total if normal_total > 0 else 0
        n_actual_rate = normal_actual / normal_total if normal_total > 0 else 0

        # st.metric の代わりに st.markdown でフォントサイズを小さく調整
        st.markdown(
            f"""
            <div style="margin-bottom: 0.8rem;">
                <span style="font-size: 0.85rem; color: #666;">通常所持</span><br>
                <span style="font-size: 1.2rem; font-weight: bold;">{normal_owned} / {normal_total} パーツ ({n_rate*100:.1f}%)</span>
            </div>
            <div style="margin-bottom: 0.5rem;">
                <span style="font-size: 0.85rem; color: #666;">実質（内定込み）</span><br>
                <span style="font-size: 1.2rem; font-weight: bold; color: #0066cc;">{normal_actual} / {normal_total} パーツ ({n_actual_rate*100:.1f}%)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(n_actual_rate)

      with col_c:
        st.markdown("### 🎯 チャンスコーデ")
        c_rate = chance_owned / chance_total if chance_total > 0 else 0
        c_actual_rate = chance_actual / chance_total if chance_total > 0 else 0

        st.markdown(
            f"""
            <div style="margin-bottom: 0.8rem;">
                <span style="font-size: 0.85rem; color: #666;">通常所持</span><br>
                <span style="font-size: 1.2rem; font-weight: bold;">{chance_owned} / {chance_total} パーツ ({c_rate*100:.1f}%)</span>
            </div>
            <div style="margin-bottom: 0.5rem;">
                <span style="font-size: 0.85rem; color: #666;">実質（内定込み）</span><br>
                <span style="font-size: 1.2rem; font-weight: bold; color: #0066cc;">{chance_actual} / {chance_total} パーツ ({c_actual_rate*100:.1f}%)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.progress(c_actual_rate)
          
      st.markdown("---")

      filter_status = st.radio(
          "表示切替",
          ["すべて表示", "所持のみ", "未所持のみ", "🆗内定のみ"],
          horizontal=True,
      )

      display_df = check_df.drop(columns=["種別"])  # 表からは種別カラムを隠す
      if filter_status == "所持のみ":
        display_df = display_df[display_df["状態"] == "✅ 所持"]
      elif filter_status == "未所持のみ":
        display_df = display_df[display_df["状態"] == "❌ 未所持"]
      elif filter_status == "🆗内定のみ":
        display_df = display_df[display_df["状態"] == "🆗内定"]

      st.dataframe(display_df, use_container_width=True)

    except Exception as e:
      st.error(
          f"外部CSVの読み込みに失敗しました。URLやファイルの公開設定をご確認ください: {e}"
      )

# ---------------------------------------------------------
# 4. チャンスコード集画面
# ---------------------------------------------------------
elif menu == "🎯 チャンスコード集":
  st.header("🎯 チャンスコード集（チャンス本体）")
  st.write("「チャンス本体」属性を持つ登録済みQRコードの一覧・検索場所です。")

  if data.empty:
    st.info("データが登録されていません。")
  else:
    chance_data = data[
        data["attribute"].apply(
            lambda x: "チャンス本体" in get_attr_list(str(x))
        )
    ].copy()

    if chance_data.empty:
      st.info("「チャンス本体」属性を持つプリフォトはまだ登録されていません。")
    else:
      search_keyword_c = st.text_input("チャンスコードをコーデ名・キャラ名で検索")
      filter_bullet_c = st.selectbox(
          "弾数で絞り込み (チャンス)", ["すべて"] + list(chance_data["bullet"].unique())
      )
      cols_per_row_c = st.slider(
          "横に並べるカードの数 (チャンス)",
          min_value=2,
          max_value=6,
          value=3,
          key="chance_slider",
      )

      if cols_per_row_c <= 3:
        c_title_fs = "1.0rem"
        c_sub_fs = "0.85rem"
      elif cols_per_row_c == 4:
        c_title_fs = "0.9rem"
        c_sub_fs = "0.75rem"
      else:
        c_title_fs = "0.8rem"
        c_sub_fs = "0.65rem"

      filtered_chance = chance_data.copy()
      if search_keyword_c:
        filtered_chance = filtered_chance[
            filtered_chance["code_name"].str.contains(
                search_keyword_c, na=False
            )
            | filtered_chance["character"].str.contains(
                search_keyword_c, na=False
            )
        ]
      if filter_bullet_c != "すべて":
        filtered_chance = filtered_chance[
            filtered_chance["bullet"] == filter_bullet_c
        ]

      st.write(f"表示件数: **{len(filtered_chance)}** 枚")

      for idx, (i, row) in enumerate(filtered_chance.iterrows()):
        if idx % cols_per_row_c == 0:
          col = st.columns(cols_per_row_c)

        with col[idx % cols_per_row_c]:
          st.markdown(
              f"<p style='font-size: {c_title_fs}; font-weight: bold; margin-bottom: 0.2rem;'>{row['code_name']}</p>",
              unsafe_allow_html=True,
          )

          if pd.notna(row["image_base64"]) and row["image_base64"] != "":
            try:
              image_bytes = base64.b64decode(row["image_base64"])
              st.markdown(
                  f"""
                          <div style="background-color: #ffffff; padding: 6px; border-radius: 6px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 0.3rem;">
                              <img src="data:image/png;base64,{base64.b64encode(image_bytes).decode('utf-8')}" style="width: 100%; max-width: 320px; height: auto; image-rendering: pixelated; image-rendering: crisp-edges; display: block; margin: 0 auto;">
                          </div>
                          """,
                  unsafe_allow_html=True,
              )
            except:
              st.warning("画像エラー")
          else:
            st.info("📷 画像なし")

          char_text = (
              f"👤 {row['character']}"
              if row.get("character", "") != ""
              else "👤 なし"
          )
          attr_text = (
              f"✨ {row['attribute']}"
              if row.get("attribute", "") != ""
              else ""
          )
          st.markdown(
              f"<p style='font-size: {c_sub_fs}; color: #555; margin: 0;'>{char_text} / {attr_text}</p>"
              f"<p style='font-size: {c_sub_fs}; color: #555; margin-bottom: 0.5rem;'>🏷️ {row['bullet']} /👗 {row.get('part', '')}</p>",
              unsafe_allow_html=True,
          )

          b_col1, b_col2 = st.columns(2)
          with b_col1:
            if st.button("✏️ 編集", key=f"c_edit_btn_{row['id']}"):
              st.session_state[f"editing_{row['id']}"] = True
          with b_col2:
            if st.button("🗑️ 削除", key=f"c_del_{row['id']}"):
              data = data[data["id"] != row["id"]]
              save_data(data)
              st.success("削除しました！")
              st.rerun()

          if st.session_state.get(f"editing_{row['id']}", False):
            with st.form(key=f"c_edit_form_{row['id']}"):
              st.markdown(f"**ID: {row['id']} の編集**")
              new_code_name = st.text_input("コーデ名", value=row["code_name"])

              current_attrs = get_attr_list(row["attribute"])
              valid_default_attrs = [
                  a for a in current_attrs if a in ATTRIBUTE_OPTIONS
              ]

              new_attributes = st.multiselect(
                  "属性（複数選択可）",
                  ATTRIBUTE_OPTIONS,
                  default=valid_default_attrs,
              )

              bullet_idx = (
                  ALL_BULLET_OPTIONS.index(row["bullet"])
                  if row["bullet"] in ALL_BULLET_OPTIONS
                  else 0
              )
              part_idx = (
                  PART_OPTIONS.index(row.get("part", "アクセ"))
                  if row.get("part", "アクセ") in PART_OPTIONS
                  else 0
              )

              new_bullet = st.selectbox(
                  "弾数", ALL_BULLET_OPTIONS, index=bullet_idx
              )
              new_part = st.selectbox("部位", PART_OPTIONS, index=part_idx)
              new_character = st.text_input(
                  "キャラクター名", value=row.get("character", "")
              )

              col_save, col_cancel = st.columns(2)
              with col_save:
                if st.form_submit_button("保存"):
                  combined_attr = (
                      ",".join(new_attributes) if new_attributes else ""
                  )
                  data.loc[data["id"] == row["id"], "code_name"] = (
                      new_code_name
                  )
                  data.loc[data["id"] == row["id"], "attribute"] = combined_attr
                  data.loc[data["id"] == row["id"], "bullet"] = new_bullet
                  data.loc[data["id"] == row["id"], "part"] = new_part
                  data.loc[data["id"] == row["id"], "character"] = (
                      new_character
                  )
                  save_data(data)
                  st.session_state[f"editing_{row['id']}"] = False
                  st.success("更新しました！")
                  st.rerun()
              with col_cancel:
                if st.form_submit_button("キャンセル"):
                  st.session_state[f"editing_{row['id']}"] = False
                  st.rerun()

          st.markdown("---")
