# JIRA Mermaid Chart Generator

JIRA API からストーリーポイントのデータを取得し、Notion で表示可能な Mermaid XY Chart を自動生成するツールです。

## 機能

- JIRA API から特定のバージョンに紐づくチケット情報を取得
- 時系列でストーリーポイントの推移を計算
- 以下の3つのラインをプロット:
  - **理想の推移**: 線形に減少する理想的な進捗ライン
  - **リリース進捗**: 全体のストーリーポイント - 完了済みストーリーポイント
  - **開発進捗**: 初期ストーリーポイント - 完了済みストーリーポイント
- Notion に直接貼り付け可能な Mermaid コードを生成

## セットアップ

### 1. 必要なパッケージのインストール

```bash
pip install -r requirements.txt
```

### 2. JIRA API トークンの取得

1. JIRA にログイン
2. アカウント設定 → セキュリティ → API トークン
3. 「トークンを作成」をクリック
4. トークンをコピーして安全な場所に保存

### 3. Story Point フィールド ID の確認

Story Point のカスタムフィールド ID は環境によって異なります。以下の方法で確認できます:

**方法1: JIRA UI から確認**
1. JIRA でチケットを開く
2. Story Point フィールドにカーソルを合わせる
3. ブラウザの開発者ツールで要素を調査
4. `customfield_xxxxx` の形式で ID を確認

**方法2: API で確認**
```bash
curl -u your-email@example.com:your-api-token \
  https://your-domain.atlassian.net/rest/api/3/field \
  | grep -i "story"
```

一般的には `customfield_10016` ですが、環境によって異なる場合があります。

## 使い方

### 環境変数の設定

```bash
# 必須
export JIRA_URL="https://your-domain.atlassian.net"
export JIRA_USERNAME="your-email@example.com"
export JIRA_API_TOKEN="your-api-token-here"
export JIRA_PROJECT_KEY="PROJ"
export JIRA_VERSION_NAME="Release 1.0"

# オプション
export JIRA_STORY_POINT_FIELD="customfield_10016"  # デフォルト値
export JIRA_START_DATE="2024-01-01"  # デフォルト: 90日前
export JIRA_END_DATE="2024-12-31"    # デフォルト: 今日
export JIRA_INTERVAL_DAYS="7"         # デフォルト: 7日（1週間）
```

### スクリプトの実行

```bash
python jira_mermaid_chart_generator.py
```

実行すると、以下のような出力が得られます:

```
JIRA からデータを取得中...
  プロジェクト: PROJ
  バージョン: Release 1.0
  取得チケット数: 123

================================================================================
生成された Mermaid チャートコード:
================================================================================
xychart-beta
    title "進捗率(開発完了, 移行完了)"
    x-axis "日付" ["01/01", "01/08", "01/15", ...]
    y-axis "残ストーリーポイント" 0 --> 867
    %% 理想の推移
    line [817.00, 748.92, 680.83, ...]
    %% リリース進捗の推移(残完了ストーリーポイント)
    line [817.00, 814.00, 814.00, ...]
    %% 開発進捗の推移(残開発完了ストーリーポイント)
    line [817.00, 814.00, 811.00, ...]
================================================================================

チャートコードを mermaid_chart.txt に保存しました。
```

### Notion への貼り付け

1. Notion ページを開く
2. `/code` と入力してコードブロックを作成
3. 言語として **Mermaid** を選択
4. 生成されたコードを貼り付け

## 設定オプション

### 必須の環境変数

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `JIRA_URL` | JIRA インスタンスの URL | `https://your-domain.atlassian.net` |
| `JIRA_USERNAME` | JIRA ユーザー名（メールアドレス） | `user@example.com` |
| `JIRA_API_TOKEN` | JIRA API トークン | `ATATTxxxxx` |
| `JIRA_PROJECT_KEY` | プロジェクトキー | `PROJ` |
| `JIRA_VERSION_NAME` | バージョン名 | `Release 1.0` |

### オプションの環境変数

| 変数名 | 説明 | デフォルト値 |
|--------|------|-------------|
| `JIRA_STORY_POINT_FIELD` | Story Point のカスタムフィールド ID | `customfield_10016` |
| `JIRA_START_DATE` | 開始日（YYYY-MM-DD形式） | 90日前 |
| `JIRA_END_DATE` | 終了日（YYYY-MM-DD形式） | 今日 |
| `JIRA_INTERVAL_DAYS` | データポイント間の日数 | `7`（1週間） |

## 完了の判定基準

以下のいずれかの条件を満たすチケットを「完了済み」として扱います:

1. ステータスが以下のいずれか:
   - Done
   - Closed
   - Resolved
   - 完了
   - クローズ

2. 解決日（Resolution Date）が設定されており、集計日時よりも前の場合

必要に応じて、スクリプト内の `completed_statuses` リストを編集してください。

## トラブルシューティング

### チケットが見つからない場合

1. プロジェクトキーが正しいか確認
2. バージョン名が正しいか確認（大文字小文字を含めて完全一致）
3. JIRA の検索画面で以下の JQL を実行して確認:
   ```
   project = "YOUR_PROJECT" AND fixVersion = "YOUR_VERSION"
   ```

### Story Point が取得できない場合

1. `JIRA_STORY_POINT_FIELD` 環境変数が正しいか確認
2. チケットに Story Point が実際に入力されているか確認
3. Story Point フィールドが数値型であることを確認

### 認証エラーが発生する場合

1. API トークンが有効か確認
2. ユーザー名（メールアドレス）が正しいか確認
3. JIRA URL が正しいか確認（末尾のスラッシュは不要）

## カスタマイズ

### データポイントの間隔を変更

スプリント期間が2週間の場合:

```bash
export JIRA_INTERVAL_DAYS="14"
```

### チャートタイトルを変更

スクリプト内の `generate_mermaid_chart` メソッドの `chart_title` パラメータを変更してください。

### 完了ステータスを追加

スクリプト内の以下の行を編集:

```python
completed_statuses = ['Done', 'Closed', 'Resolved', '完了', 'クローズ', 'Your Custom Status']
```

## ライセンス

MIT License

## サポート

問題が発生した場合は、Issue を作成してください。

