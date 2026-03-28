import os
import io
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage
import google.generativeai as genai
from PIL import Image

app = Flask(__name__)

# 環境変数から鍵を読み込む
LINE_ACCESS_TOKEN = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
LINE_SECRET = os.environ["LINE_CHANNEL_SECRET"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

line_bot_api = LineBotApi(LINE_ACCESS_TOKEN)
handler = WebhookHandler(LINE_SECRET)
genai.configure(api_key=GEMINI_API_KEY)

# Gemini 2.5 Flashモデルを指定 (画像解析が得意)
model = genai.GenerativeModel('gemini-2.5-flash')

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

# --- テキストメッセージを受信したときの処理 (基本はそのまま) ---
@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    # AIに返信を考えさせる (プロンプトを少し画像解析寄りに修正)
    prompt = f"あなたは優秀なAIアシスタントです。ユーザーからの質問に、親切かつ簡潔に答えてください：\n{event.message.text}"
    response = model.generate_content(prompt)
    
    # LINEに返信する
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response.text)
    )

# --- 【新規追加】画像メッセージを受信したときの処理 ---
@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    # LINEサーバーから画像データを取得
    message_content = line_bot_api.get_message_content(event.message.id)
    
    # 画像データをバイナリ（BytesIO）として読み込む
    image_bytes = io.BytesIO(message_content.content)
    
    # PIL (Pillow) ライブラリで画像オブジェクトに変換
    pil_image = Image.open(image_bytes)
    
    # Geminiに画像とプロンプトを送る
    # プロンプトは「この画像は何？」という指示
    prompt = "この画像には何が写っていますか？日本語で、具体的かつ分かりやすく説明してください。もし食べ物ならレシピのヒントも添えて。"
    
    # 画像とテキストを一緒に送る
    response = model.generate_content([prompt, pil_image])
    
    # Geminiの解析結果をLINEに返信する
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response.text)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
