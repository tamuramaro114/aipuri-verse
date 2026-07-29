import base64
import io
import os
import cv2
from google.oauth2.service_account import Credentials
import gspread
import numpy as np
import pandas as pd
from PIL import Image
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
    # st.secrets["gcp_service_account"] から認証情報を取得
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    client = gspread.authorize(creds)

    # Secretsのセクション内、またはルートのどちらからでも安全に取得
    if "sheet_name" in st.secrets.get("gcp_service_account", {}):
      target = st.secrets["gcp_service_account"]["sheet_name"]
    else:
      target = st.secrets.get("sheet_name", "aipri_database")

    # ID（キー）かファイル名かで開く方法を自動で切り替え
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


# データの読み込み関数（Googleスプレッドシートから取得）
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


# データの保存関数（Googleスプレッドシートへ書き込み）
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


# アップロードされた画像からQRコードを読み取り、クリーンなQRコード画像を生成する関数
def process_and_optimize_qr(uploaded_image):
  try:
    image = Image.open(uploaded_image)
    if image.mode in ("RGBA", "P"):
      image = image.convert("RGB")

    img_np = np.array(image)
    if len(img_np.shape) == 3 and img_np.shape[2] == 3:
      img_cv = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
    else:
      img_cv = img_np

    detector = cv2.QRCodeDetector()
    data, bbox, rectified_image = detector.detectAndDecode(img_cv)

    if data:
      qr = qrcode.QRCode(
          version=None,
          error_correction=qrcode.constants.ERROR_CORRECT_M,
          box_size=4,
          border=2,
      )
      qr.add_data(data)
      qr.make(fit=True)

      qr_img = qr.make_image(fill_color="black", back_color="white")

      output = io.BytesIO()
      qr_img.save(output, format="PNG")
      return (
          output.getvalue(),
          "success",
          f"QRコードを正常に読み取りました！ (データ内容: {data[:20]}...)",
      )
    else:
      max_size = 500
      if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

      output = io.BytesIO()
      image.save(output, format="JPEG", quality=80)
      return (
          output.getvalue(),
          "fallback",
          "⚠️"
          " QRコードの読み取りに失敗したため、画像を圧縮して保存しました。",
      )

  except Exception as e:
    image = Image.open(uploaded_image)
    if image.mode in ("RGBA", "P"):
      image = image.convert("RGB")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=80)
    return output.getvalue(), "error", f"処理中にエラーが発生しました: {e}"


data = load_data()

st.title("✨ アイプリバース プリフォト管理アプリ (スプレッドシート連携版) ✨")
st.sidebar.header("メニュー")
menu = st.sidebar.radio(
    "選択してください", ["コレクション一覧・検索", "プリフォトを追加する"]
)

# --- サイドバー：データ管理 ---
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

# 弾数や属性などの選択肢定義
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
    "チャンスコーデ",
    "コラボ",
    "フルコーデ",
    "ミルフィー",
    "グミ",
]
PART_OPTIONS = ["アクセ", "ワンピース", "トップス", "ボトムス", "シューズ"]
PART_SORT_ORDER = {
    "アクセ": 1,
    "ワンピース": 2,
    "トップス": 3,
    "ボトムス": 4,
    "シューズ": 5,
}

# ---------------------------------------------------------
# 1. コレクション一覧・検索画面
# ---------------------------------------------------------
if menu == "コレクション一覧・検索":
  st.header("📖 マイ・プリフォトコレクション")

  if data.empty:
    st.info(
        "まだプリフォトが登録されていません。「プリフォトを追加する」から登録してみましょう！"
    )
  else:
    st.sidebar.subheader("🔍 絞り込み検索 & 設定")

    sort_option = st.sidebar.selectbox(
        "並べ替え",
        [
            "コーデ名順 (アクセ→服→靴)",
            "50音順 (コーデ名)",
            "弾の早い順 (昇順)",
            "弾の遅い順 (降順)",
            "登録順 (新しい順)",
            "登録順 (古い順)",
        ],
    )

    cols_per_row = st.sidebar.slider(
        "横に並べるカードの数", min_value=2, max_value=6, value=3
    )

    existing_bullets = [
        b for b in ALL_BULLET_OPTIONS if b in data["bullet"].values
    ]
    other_bullets = [
        b for b in data["bullet"].dropna().unique() if b not in ALL_BULLET_OPTIONS
    ]
    all_bullet_choices = ["すべて"] + existing_bullets + other_bullets

    selected_bullet = st.sidebar.selectbox("弾数で絞り込み", all_bullet_choices)

    existing_attrs = [
        a
        for a in ATTRIBUTE_OPTIONS
        if "attribute" in data.columns and a in data["attribute"].values
    ]
    all_attr_choices = ["すべて"] + existing_attrs
    selected_attr = st.sidebar.selectbox("属性で絞り込み", all_attr_choices)

    existing_parts = [
        p
        for p in PART_OPTIONS
        if "part" in data.columns and p in data["part"].values
    ]
    all_part_choices = ["すべて"] + existing_parts
    selected_part = st.sidebar.selectbox("部位で絞り込み", all_part_choices)

    search_keyword = st.sidebar.text_input("コーデ名・キャラ名で検索")

    filtered_data = data.copy()
    if selected_bullet != "すべて":
      filtered_data = filtered_data[filtered_data["bullet"] == selected_bullet]
    if selected_attr != "すべて" and "attribute" in filtered_data.columns:
      filtered_data = filtered_data[
          filtered_data["attribute"] == selected_attr
      ]
    if selected_part != "すべて" and "part" in filtered_data.columns:
      filtered_data = filtered_data[filtered_data["part"] == selected_part]
    if search_keyword:
      filtered_data = filtered_data[
          filtered_data["code_name"].str.contains(search_keyword, na=False)
          | filtered_data["character"].str.contains(search_keyword, na=False)
      ]

    filtered_data["part_sort_val"] = (
        filtered_data["part"].map(PART_SORT_ORDER).fillna(99)
    )

    if sort_option == "コーデ名順 (アクセ→服→靴)":
      filtered_data = filtered_data.sort_values(
          by=["code_name", "part_sort_val"], ascending=[True, True]
      )
    elif sort_option == "50音順 (コーデ名)":
      filtered_data = filtered_data.sort_values(by="code_name", ascending=True)
    elif sort_option == "弾の早い順 (昇順)":
      filtered_data = filtered_data.sort_values(by="bullet", ascending=True)
    elif sort_option == "弾の遅い順 (降順)":
      filtered_data = filtered_data.sort_values(by="bullet", ascending=False)
    elif sort_option == "登録順 (新しい順)":
      filtered_data = filtered_data.sort_values(by="id", ascending=False)
    elif sort_option == "登録順 (古い順)":
      filtered_data = filtered_data.sort_values(by="id", ascending=True)

    st.write(
        f"全 **{len(data)}** 枚中 / 表示件数: **{len(filtered_data)}** 枚"
    )

    font_sizes = {
        2: {"title": "1.5rem", "body": "1.0rem"},
        3: {"title": "1.3rem", "body": "0.9rem"},
        4: {"title": "1.1rem", "body": "0.8rem"},
        5: {"title": "0.95rem", "body": "0.75rem"},
        6: {"title": "0.85rem", "body": "0.7rem"},
    }
    current_sizes = font_sizes.get(
        cols_per_row, {"title": "1.2rem", "body": "0.9rem"}
    )
    title_size = current_sizes["title"]
    body_size = current_sizes["body"]

    for idx, (i, row) in enumerate(filtered_data.iterrows()):
      if idx % cols_per_row == 0:
        col = st.columns(cols_per_row)

      with col[idx % cols_per_row]:
        st.markdown(
            f"<p style='font-size: {title_size}; font-weight: bold;"
            f" margin-bottom: 0.5rem;'>{row['code_name']}</p>",
            unsafe_allow_html=True,
        )

        if pd.notna(row["image_base64"]) and row["image_base64"] != "":
          try:
            image_bytes = base64.b64decode(row["image_base64"])
            st.image(image_bytes, use_container_width=True)
          except:
            st.warning("画像読み込みエラー")
        else:
          st.info("📷 画像なし")

        info_html = f"""
                <div style='font-size: {body_size}; line-height: 1.4; margin-bottom: 0.5rem;'>
                    🏷️ <b>弾数:</b> {row['bullet']}<br>
                    ⭐ <b>属性:</b> {row.get('attribute', 'つうじょう')}<br>
                    👗 <b>部位:</b> {row.get('part', 'ワンピース')}<br>
                    🎤 <b>キャラクター:</b> {row.get('character', '')}
                </div>
                """
        st.markdown(info_html, unsafe_allow_html=True)

        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:
          edit_key = f"edit_mode_{row['id']}"
          if st.button("編集", key=f"btn_edit_{row['id']}"):
            st.session_state[edit_key] = not st.session_state.get(
                edit_key, False
            )

        with btn_col2:
          if st.button("削除", key=f"del_{row['id']}"):
            data = data[data["id"] != row["id"]]
            save_data(data)
            st.success("削除しました！画面を更新してください。")
            st.rerun()

        if st.session_state.get(f"edit_mode_{row['id']}", False):
          with st.form(key=f"form_edit_{row['id']}"):
            st.markdown("---")
            st.write("✏️ **内容の編集**")

            new_code_name = st.text_input("コーデ名", value=row["code_name"])

            attr_val = (
                row["attribute"]
                if "attribute" in row and pd.notna(row["attribute"])
                else "つうじょう"
            )
            a_idx = (
                ATTRIBUTE_OPTIONS.index(attr_val)
                if attr_val in ATTRIBUTE_OPTIONS
                else 0
            )
            new_attribute = st.selectbox(
                "属性", ATTRIBUTE_OPTIONS, index=a_idx, key=f"ea_{row['id']}"
            )

            if new_attribute == "ミルフィー":
              current_bullets = MILLEFEE_BULLET_OPTIONS
            elif new_attribute == "グミ":
              current_bullets = GUMMI_BULLET_OPTIONS
            else:
              current_bullets = NORMAL_BULLET_OPTIONS

            b_val = row["bullet"]
            b_idx = (
                current_bullets.index(b_val)
                if b_val in current_bullets
                else 0
            )
            new_bullet = st.selectbox(
                "弾数", current_bullets, index=b_idx, key=f"eb_{row['id']}"
            )

            part_val = (
                row["part"]
                if "part" in row and pd.notna(row["part"])
                else "ワンピース"
            )
            p_idx = (
                PART_OPTIONS.index(part_val) if part_val in PART_OPTIONS else 0
            )
            new_part = st.selectbox(
                "部位", PART_OPTIONS, index=p_idx, key=f"ep_{row['id']}"
            )

            char_val = (
                row["character"] if pd.notna(row["character"]) else ""
            )
            new_character = st.text_input(
                "キャラクター", value=char_val, key=f"ec_{row['id']}"
            )

            new_image = st.file_uploader(
                "画像を変更する場合のみ選択",
                type=["jpg", "png", "jpeg"],
                key=f"ei_{row['id']}",
            )

            if st.form_submit_button("更新を保存"):
              data.loc[data["id"] == row["id"], "code_name"] = new_code_name
              data.loc[data["id"] == row["id"], "bullet"] = new_bullet
              data.loc[data["id"] == row["id"], "attribute"] = new_attribute
              data.loc[data["id"] == row["id"], "part"] = new_part
              data.loc[data["id"] == row["id"], "character"] = new_character

              if new_image is not None:
                opt_bytes, _, _ = process_and_optimize_qr(new_image)
                new_base64 = base64.b64encode(opt_bytes).decode("utf-8")
                data.loc[data["id"] == row["id"], "image_base64"] = new_base64

              save_data(data)
              st.session_state[edit_key] = False
              st.success("更新しました！画面を更新してください。")
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
      "プリフォトの画像 (スマホの写真など)", type=["jpg", "png", "jpeg"]
  )

  processed_bytes = None
  if uploaded_image is not None:
    file_base_name = os.path.splitext(uploaded_image.name)[0]
    st.info(f"📁 アップロードされたファイル名: `{uploaded_image.name}`")

    with st.spinner("🤖 QRコードを解析し、高精度・超軽量な画像に変換中..."):
      processed_bytes, status, msg = process_and_optimize_qr(uploaded_image)

    if status == "success":
      st.success(msg)
    else:
      st.warning(msg)

    st.write("🖼️ **変換後のプレビュー (軽量化済み):**")
    st.image(processed_bytes, width=250)

    if st.button("✨ ファイル名をコーデ名として使う"):
      st.session_state["code_name_input"] = file_base_name
      st.rerun()

  with st.form("add_form", clear_on_submit=True):
    code_name = st.text_input(
        "コーデ名", value=st.session_state["code_name_input"]
    )

    attribute = st.radio("属性を選択", ATTRIBUTE_OPTIONS, horizontal=True)

    if attribute == "ミルフィー":
      bullet = st.radio(
          "弾数を選択 (ミルフィー)", MILLEFEE_BULLET_OPTIONS, horizontal=True
      )
    elif attribute == "グミ":
      bullet = st.radio("弾数を選択 (グミ)", GUMMI_BULLET_OPTIONS, horizontal=True)
    else:
      bullet = st.radio("弾数を選択", NORMAL_BULLET_OPTIONS, horizontal=True)

    part = st.radio("部位を選択", PART_OPTIONS, horizontal=True)

    character = st.text_input(
        "映っているキャラクター名 (マイキャラ / アニメキャラ名)"
    )

    submitted = st.form_submit_button("登録する")

    if submitted:
      if not code_name:
        st.error("コーデ名を入力してください。")
      elif uploaded_image is None or processed_bytes is None:
        st.error("画像をアップロードしてください。")
      else:
        new_id = (
            int(data["id"].max() + 1)
            if not data.empty and not pd.isna(data["id"].max())
            else 1
        )

        image_base64 = base64.b64encode(processed_bytes).decode("utf-8")

        new_row = pd.DataFrame({
            "id": [new_id],
            "code_name": [code_name],
            "bullet": [bullet],
            "attribute": [attribute],
            "part": [part],
            "character": [character],
            "image_base64": [image_base64],
        })

        data = pd.concat([data, new_row], ignore_index=True)
        save_data(data)

        st.session_state["code_name_input"] = ""
        st.success("✨ プリフォトをスプレッドシートに正常に登録しました！")