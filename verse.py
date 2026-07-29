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
    image = Image.open(uploaded_image)
    if image.mode in ("RGBA", "P"):
      image = image.convert("RGB")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue(), "error", f"処理中エラー: {e}"


data = load_data()

st.title("✨ アイプリバース プリフォト管理アプリ ✨")
st.sidebar.header("メニュー")
menu = st.sidebar.radio(
    "選択してください",
    [
        "コレクション一覧・検索",
        "プリフォトを追加する",
        "🎯 弾別コンプリート状況",
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
    "チャンスコーデ",
    "コラボ",
    "フルコーデ",
    "ミルフィー",
    "グミ",
]
# 部位に「フルコーデ」を追加しました
PART_OPTIONS = [
    "アクセ",
    "ワンピース",
    "トップス",
    "ボトムス",
    "シューズ",
    "フルコーデ",
]

# ---------------------------------------------------------
# 1. コレクション一覧・検索画面（編集・削除機能付き）
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

    filtered_data = data.copy()

    if search_keyword:
      filtered_data = filtered_data[
          filtered_data["code_name"].str.contains(search_keyword, na=False)
          | filtered_data["character"].str.contains(search_keyword, na=False)
      ]

    if selected_attribute != "すべて":
      filtered_data = filtered_data[
          filtered_data["attribute"] == selected_attribute
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
        f"全 **{len(data)}** 枚中 / 表示件数: **{len(filtered_data)}** 枚"
    )

    for idx, (i, row) in enumerate(filtered_data.iterrows()):
      if idx % cols_per_row == 0:
        col = st.columns(cols_per_row)

      with col[idx % cols_per_row]:
        st.markdown(
            f"<p style='font-weight: bold; margin-bottom: 0.2rem;'>{row['code_name']}</p>",
            unsafe_allow_html=True,
        )

        if pd.notna(row["image_base64"]) and row["image_base64"] != "":
          try:
            image_bytes = base64.b64decode(row["image_base64"])
            encoded_grid_img = base64.b64encode(image_bytes).decode("utf-8")
            st.markdown(
                f"""
                        <div style="background-color: #ffffff; padding: 8px; border-radius: 6px; border: 1px solid #e0e0e0; text-align: center; margin-bottom: 0.3rem;">
                            <img src="data:image/png;base64,{encoded_grid_img}" style="width: 100%; max-width: 320px; height: auto; image-rendering: pixelated; image-rendering: crisp-edges; display: block; margin: 0 auto;">
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
            f"<p style='font-size: 0.85rem; color: #555; margin: 0;'>{char_text} / {attr_text}</p>"
            f"<p style='font-size: 0.85rem; color: #555; margin-bottom: 0.5rem;'>🏷️ {row['bullet']} / {row.get('part', '')}</p>",
            unsafe_allow_html=True,
        )

        # 編集・削除ボタンを2カラムで配置
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

        # 編集フォーム（編集ボタンが押されたときのみ展開）
        if st.session_state.get(f"editing_{row['id']}", False):
          with st.form(key=f"edit_form_{row['id']}"):
            st.markdown(f"**ID: {row['id']} の編集**")
            new_code_name = st.text_input("コーデ名", value=row["code_name"])

            # 既存の選択肢のインデックスを取得（範囲外エラー防止の安全策付き）
            attr_idx = (
                ATTRIBUTE_OPTIONS.index(row["attribute"])
                if row["attribute"] in ATTRIBUTE_OPTIONS
                else 0
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

            new_attribute = st.selectbox(
                "属性", ATTRIBUTE_OPTIONS, index=attr_idx
            )
            new_bullet = st.selectbox("弾数", ALL_BULLET_OPTIONS, index=bullet_idx)
            new_part = st.selectbox("部位", PART_OPTIONS, index=part_idx)
            new_character = st.text_input(
                "キャラクター名", value=row.get("character", "")
            )

            col_save, col_cancel = st.columns(2)
            with col_save:
              if st.form_submit_button("保存"):
                data.loc[data["id"] == row["id"], "code_name"] = new_code_name
                data.loc[data["id"] == row["id"], "attribute"] = new_attribute
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
    attribute = st.radio("属性", ATTRIBUTE_OPTIONS, horizontal=True)
    bullet = st.radio("弾数", ALL_BULLET_OPTIONS, horizontal=True)
    part = st.radio("部位", PART_OPTIONS, horizontal=True)
    character = st.text_input("キャラクター名")

    if st.form_submit_button("登録する"):
      if not code_name or uploaded_image is None:
        st.error("コーデ名と画像を入力してください。")
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
        st.success("✨ 登録しました！")

# ---------------------------------------------------------
# 3. 弾別コンプリート状況（外部CSV対応）
# ---------------------------------------------------------
elif menu == "🎯 弾別コンプリート状況":
  st.header("🎯 弾別コンプリート状況チェッカー")
  st.write(
      "外部（GitHubなど）に配置した各弾のマスターCSVを読み込み、所持状況をチェックします。"
  )

  # 📌 ここに新しい弾のCSVを追加していくことができます
  bullet_csv_urls = {
      "おねがい2だ": (
          "https://raw.githubusercontent.com/tamuramaro114/aipuri-verse/main/aipri_master/onegai2_master.csv"
      ),
      "おねがい3だん": (
          "https://raw.githubusercontent.com/tamuramaro114/aipuri-verse/main/aipri_master/onegai3_master.csv"  # ←必要に応じてファイル名に合わせて変更してください
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
      owned_count = 0

      for _, row in master_df.iterrows():
        code_name = str(row["code_name"]).strip()
        # CSVに attribute がない場合の安全策として .get を使用
        attribute = str(row.get("attribute", "つうじょう")).strip()
        part = str(row["part"]).strip()

        # 所持判定（コーデ名と部位で判定）
        match = owned_df[
            (owned_df["code_name"] == code_name) & (owned_df["part"] == part)
        ]
        is_owned = not match.empty
        if is_owned:
          owned_count += 1

        checked_list.append({
            "コーデ名": code_name,
            "属性": attribute,  # ← 属性を表示項目に追加
            "部位": part,
            "状態": "✅ 所持" if is_owned else "❌ 未所持",
        })

      check_df = pd.DataFrame(checked_list)

      total_items = len(master_df)
      progress_rate = owned_count / total_items if total_items > 0 else 0

      st.metric(
          label=f"{selected_bullet_target} コンプリート進捗",
          value=(
              f"{owned_count} / {total_items} パーツ"
              f" ({progress_rate*100:.1f}%)"
          ),
      )
      st.progress(progress_rate)

      filter_status = st.radio(
          "表示切替", ["すべて表示", "所持のみ", "未所持のみ"], horizontal=True
      )

      display_df = check_df.copy()
      if filter_status == "所持のみ":
        display_df = display_df[display_df["状態"] == "✅ 所持"]
      elif filter_status == "未所持のみ":
        display_df = display_df[display_df["状態"] == "❌ 未所持"]

      st.dataframe(display_df, use_container_width=True)

    except Exception as e:
      st.error(
          f"外部CSVの読み込みに失敗しました。URLやファイルの公開設定をご確認ください: {e}"
      )
