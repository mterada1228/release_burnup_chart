#!/bin/bash
# JIRA のカスタムフィールド一覧を取得する REST API スクリプト

# 色の定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# .env ファイルから環境変数を読み込む
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 必須環境変数のチェック
if [ -z "$JIRA_URL" ] || [ -z "$JIRA_USERNAME" ] || [ -z "$JIRA_API_TOKEN" ]; then
    echo -e "${RED}エラー: 以下の環境変数を設定してください:${NC}"
    echo "  JIRA_URL: JIRA インスタンスの URL"
    echo "  JIRA_USERNAME: JIRA ユーザー名（メールアドレス）"
    echo "  JIRA_API_TOKEN: JIRA API トークン"
    exit 1
fi

# プロジェクトキーを引数から取得
PROJECT_KEY="${1:-$JIRA_PROJECT_KEY}"

echo -e "${BLUE}=====================================================================================================${NC}"
echo -e "${GREEN}JIRA カスタムフィールド一覧取得${NC}"
echo -e "${BLUE}=====================================================================================================${NC}"
echo ""

# jq がインストールされているか確認
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}警告: jq がインストールされていません。出力が整形されません。${NC}"
    echo "  インストール: brew install jq (macOS) または apt install jq (Linux)"
    echo ""
    USE_JQ=false
else
    USE_JQ=true
fi

# 全てのフィールドを取得
echo -e "${GREEN}1. 全てのフィールドを取得中...${NC}"
FIELDS_JSON=$(curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
    -H "Accept: application/json" \
    "$JIRA_URL/rest/api/3/field")

if [ $? -ne 0 ]; then
    echo -e "${RED}エラー: JIRA API への接続に失敗しました${NC}"
    exit 1
fi

# カスタムフィールドのみをフィルタリング
if [ "$USE_JQ" = true ]; then
    CUSTOM_FIELDS=$(echo "$FIELDS_JSON" | jq '[.[] | select(.id | startswith("customfield_"))]')
    CUSTOM_FIELD_COUNT=$(echo "$CUSTOM_FIELDS" | jq 'length')
    
    echo -e "${GREEN}   → カスタムフィールド: ${CUSTOM_FIELD_COUNT}件${NC}"
    echo ""
else
    # jq がない場合は単純なフィルタリング
    CUSTOM_FIELDS=$(echo "$FIELDS_JSON" | grep -o '"customfield_[^"]*"' | sort -u)
    CUSTOM_FIELD_COUNT=$(echo "$CUSTOM_FIELDS" | wc -l | tr -d ' ')
    echo -e "${GREEN}   → カスタムフィールド: ${CUSTOM_FIELD_COUNT}件${NC}"
    echo ""
fi

# プロジェクトが指定されている場合、そのプロジェクトで使用されているフィールドを確認
if [ -n "$PROJECT_KEY" ]; then
    echo -e "${GREEN}2. プロジェクト \"${PROJECT_KEY}\" で使用されているフィールドを確認中...${NC}"
    
    # プロジェクトのチケットを1件取得
    ISSUE_JSON=$(curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
        -H "Accept: application/json" \
        "$JIRA_URL/rest/api/3/search/jql?jql=project=$PROJECT_KEY&maxResults=1&fields=*all")
    
    if [ "$USE_JQ" = true ]; then
        # 実際に使用されているカスタムフィールドのみをフィルタ
        USED_CUSTOM_FIELDS=$(echo "$ISSUE_JSON" | jq -r '.issues[0].fields | keys | .[] | select(startswith("customfield_"))')
        
        if [ -z "$USED_CUSTOM_FIELDS" ]; then
            echo -e "${YELLOW}   → プロジェクトにチケットがないか、カスタムフィールドが使用されていません${NC}"
            echo ""
        else
            echo -e "${GREEN}   → 使用されているカスタムフィールド: $(echo "$USED_CUSTOM_FIELDS" | wc -l | tr -d ' ')件${NC}"
            echo ""
            
            # 使用されているフィールドの詳細を表示
            echo -e "${BLUE}=====================================================================================================${NC}"
            echo -e "${GREEN}プロジェクト \"${PROJECT_KEY}\" で使用されているカスタムフィールド${NC}"
            echo -e "${BLUE}=====================================================================================================${NC}"
            printf "%-5s %-30s %-40s %-20s\n" "No." "フィールドID" "フィールド名" "タイプ"
            echo "-----------------------------------------------------------------------------------------------------"
            
            INDEX=1
            for field_id in $USED_CUSTOM_FIELDS; do
                FIELD_INFO=$(echo "$CUSTOM_FIELDS" | jq -r ".[] | select(.id == \"$field_id\")")
                FIELD_NAME=$(echo "$FIELD_INFO" | jq -r '.name')
                FIELD_TYPE=$(echo "$FIELD_INFO" | jq -r '.schema.type // "N/A"')
                CUSTOM_TYPE=$(echo "$FIELD_INFO" | jq -r '.schema.custom // ""' | sed 's/.*://g')
                
                if [ -n "$CUSTOM_TYPE" ]; then
                    FIELD_TYPE_DISPLAY="$FIELD_TYPE ($CUSTOM_TYPE)"
                else
                    FIELD_TYPE_DISPLAY="$FIELD_TYPE"
                fi
                
                printf "%-5s %-30s %-40s %-20s\n" "$INDEX" "$field_id" "$FIELD_NAME" "$FIELD_TYPE_DISPLAY"
                INDEX=$((INDEX + 1))
            done
            
            echo -e "${BLUE}=====================================================================================================${NC}"
            echo ""
            
            # 環境変数設定例を出力
            echo -e "${GREEN}環境変数設定例:${NC}"
            echo "-----------------------------------------------------------------------------------------------------"
            
            INDEX=1
            for field_id in $USED_CUSTOM_FIELDS; do
                if [ $INDEX -le 10 ]; then
                    FIELD_INFO=$(echo "$CUSTOM_FIELDS" | jq -r ".[] | select(.id == \"$field_id\")")
                    FIELD_NAME=$(echo "$FIELD_INFO" | jq -r '.name')
                    ENV_NAME=$(echo "JIRA_${FIELD_NAME}" | tr '[:lower:]' '[:upper:]' | tr ' /-' '___' | sed 's/[^A-Z0-9_]//g')
                    echo "export ${ENV_NAME}_FIELD='${field_id}'  # ${FIELD_NAME}"
                fi
                INDEX=$((INDEX + 1))
            done
            
            if [ $INDEX -gt 11 ]; then
                echo "... 他 $((INDEX - 11)) 件"
            fi
            
            echo "-----------------------------------------------------------------------------------------------------"
        fi
    else
        echo -e "${YELLOW}   → jq がインストールされていないため、詳細を表示できません${NC}"
    fi
else
    # プロジェクトが指定されていない場合、全てのカスタムフィールドを表示
    echo -e "${GREEN}2. 全てのカスタムフィールドを表示中...${NC}"
    echo ""
    
    if [ "$USE_JQ" = true ]; then
        echo -e "${BLUE}=====================================================================================================${NC}"
        echo -e "${GREEN}全カスタムフィールド一覧${NC}"
        echo -e "${BLUE}=====================================================================================================${NC}"
        printf "%-5s %-30s %-40s %-20s\n" "No." "フィールドID" "フィールド名" "タイプ"
        echo "-----------------------------------------------------------------------------------------------------"
        
        echo "$CUSTOM_FIELDS" | jq -r 'to_entries | .[] | 
            "\(.key + 1)|\(.value.id)|\(.value.name)|\(.value.schema.type // "N/A") (\(.value.schema.custom // "" | split(":") | .[-1]))"' | 
        while IFS='|' read -r index id name type; do
            printf "%-5s %-30s %-40s %-20s\n" "$index" "$id" "$name" "$type"
        done
        
        echo -e "${BLUE}=====================================================================================================${NC}"
        echo ""
        echo -e "${YELLOW}ヒント: 特定のプロジェクトのカスタムフィールドのみを表示するには:${NC}"
        echo "  $0 <PROJECT_KEY>"
        echo "  例: $0 ougi"
    else
        echo "$CUSTOM_FIELDS"
        echo ""
        echo -e "${YELLOW}ヒント: jq をインストールすると整形された出力が表示されます${NC}"
    fi
fi

echo ""
echo -e "${GREEN}完了しました。${NC}"

