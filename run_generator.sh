#!/bin/bash

# JIRA Mermaid Chart Generator 実行スクリプト

# カラー出力設定
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}JIRA Mermaid Chart Generator${NC}"
echo -e "${GREEN}==================================================${NC}"
echo ""

# 環境変数ファイルの読み込み
if [ -f ".env" ]; then
    echo -e "${GREEN}環境変数を .env から読み込んでいます...${NC}"
    export $(cat .env | grep -v '^#' | xargs)
elif [ -f "config_template.env" ]; then
    echo -e "${YELLOW}警告: .env ファイルが見つかりません。${NC}"
    echo -e "${YELLOW}config_template.env をコピーして .env を作成し、設定を入力してください。${NC}"
    echo ""
    echo -e "コマンド例:"
    echo -e "  cp config_template.env .env"
    echo -e "  nano .env  # または vim, code など"
    echo ""
    exit 1
else
    echo -e "${YELLOW}警告: 環境変数ファイルが見つかりません。${NC}"
    echo -e "${YELLOW}環境変数を直接設定してください。${NC}"
    echo ""
fi

# 必須環境変数のチェック
REQUIRED_VARS=("JIRA_URL" "JIRA_USERNAME" "JIRA_API_TOKEN" "JIRA_PROJECT_KEY" "JIRA_VERSION_NAME")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=($var)
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo -e "${RED}エラー: 以下の環境変数が設定されていません:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo -e "  ${RED}- $var${NC}"
    done
    echo ""
    exit 1
fi

# Python のチェック
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}エラー: Python 3 がインストールされていません。${NC}"
    exit 1
fi

# 依存パッケージのインストール確認
echo -e "${GREEN}依存パッケージを確認しています...${NC}"
if ! python3 -c "import requests" &> /dev/null; then
    echo -e "${YELLOW}requests パッケージがインストールされていません。${NC}"
    echo -e "${YELLOW}インストール中...${NC}"
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo -e "${RED}エラー: パッケージのインストールに失敗しました。${NC}"
        exit 1
    fi
fi

# スクリプトの実行
echo -e "${GREEN}チャートを生成しています...${NC}"
echo ""
python3 jira_mermaid_chart_generator.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}==================================================${NC}"
    echo -e "${GREEN}完了しました！${NC}"
    echo -e "${GREEN}==================================================${NC}"
    echo ""
    echo -e "生成されたファイル: ${GREEN}mermaid_chart.txt${NC}"
    echo ""
    echo -e "${YELLOW}次のステップ:${NC}"
    echo -e "1. Notion ページを開く"
    echo -e "2. ${GREEN}/code${NC} と入力"
    echo -e "3. 言語として ${GREEN}Mermaid${NC} を選択"
    echo -e "4. ${GREEN}mermaid_chart.txt${NC} の内容を貼り付け"
    echo ""
else
    echo ""
    echo -e "${RED}==================================================${NC}"
    echo -e "${RED}エラーが発生しました${NC}"
    echo -e "${RED}==================================================${NC}"
    echo ""
    echo -e "上記のエラーメッセージを確認してください。"
    echo ""
    exit 1
fi

