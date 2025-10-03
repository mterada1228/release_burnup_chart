#!/usr/bin/env python3
"""
JIRA API からストーリーポイントを取得し、Mermaid XY Chart を生成するスクリプト
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import requests
from requests.auth import HTTPBasicAuth
import json
from dotenv import load_dotenv


class JiraMermaidChartGenerator:
    """JIRA データから Mermaid チャートを生成するクラス"""
    
    def __init__(self, jira_url: str, username: str, api_token: str):
        """
        Args:
            jira_url: JIRA インスタンスの URL (例: https://your-domain.atlassian.net)
            username: JIRA ユーザー名（メールアドレス）
            api_token: JIRA API トークン
        """
        self.jira_url = jira_url.rstrip('/')
        self.auth = HTTPBasicAuth(username, api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    def get_issues_by_version(self, project_key: str, version_name: str) -> List[Dict]:
        """
        特定のバージョンに紐づくチケット一覧を取得
        
        Args:
            project_key: プロジェクトキー (例: "PROJ")
            version_name: バージョン名 (例: "Release 1.0")
            
        Returns:
            チケット情報のリスト
        """
        # JQL クエリを構築
        jql = f'project = "{project_key}" AND fixVersion = "{version_name}"'
        
        all_issues = []
        start_at = 0
        max_results = 100
        
        while True:
            url = f"{self.jira_url}/rest/api/3/search/jql"
            params = {
                'jql': jql,
                'startAt': start_at,
                'maxResults': max_results,
                'fields': '*all'  # すべてのフィールドを取得してカスタムフィールドIDを確認
            }
            
            response = requests.get(url, headers=self.headers, auth=self.auth, params=params)
            
            if response.status_code != 200:
                print(f"エラー: JIRA API リクエストが失敗しました (ステータスコード: {response.status_code})")
                print(f"レスポンス: {response.text}")
                sys.exit(1)
            
            data = response.json()
            issues = data.get('issues', [])
            all_issues.extend(issues)
            
            # すべてのチケットを取得したか確認
            if start_at + len(issues) >= data.get('total', 0):
                break
            
            start_at += max_results
        
        return all_issues
    
    def get_all_fields(self) -> Dict:
        """
        JIRA のすべてのフィールド定義を取得
        
        Returns:
            フィールド定義の辞書 {field_id: field_name}
        """
        url = f"{self.jira_url}/rest/api/3/field"
        response = requests.get(url, headers=self.headers, auth=self.auth)
        
        if response.status_code != 200:
            print(f"警告: フィールド定義の取得に失敗しました")
            return {}
        
        fields = response.json()
        return {field['id']: field['name'] for field in fields}
    
    def get_story_point_field_id(self) -> str:
        """
        Story Point のカスタムフィールド ID を取得
        
        Returns:
            カスタムフィールド ID (例: "customfield_10016")
        """
        # デフォルトの Story Points フィールド ID
        # 環境によって異なる場合があるため、環境変数で上書き可能
        return os.getenv('JIRA_STORY_POINT_FIELD', 'customfield_10016')
    
    def get_zakkuri_point_field_id(self) -> str:
        """
        ざっくりポイントのカスタムフィールド ID を取得
        
        Returns:
            カスタムフィールド ID (例: "customfield_XXXXX")
        """
        # 環境変数で設定可能
        return os.getenv('JIRA_ZAKKURI_POINT_FIELD', '')
    
    def get_boards_for_project(self, project_key: str, board_type: str = None) -> List[Dict]:
        """
        プロジェクトに関連するボードを取得
        
        Args:
            project_key: プロジェクトキー
            board_type: ボードタイプ ('scrum', 'kanban', または None で全て)
            
        Returns:
            ボード情報のリスト
        """
        url = f"{self.jira_url}/rest/agile/1.0/board"
        params = {'projectKeyOrId': project_key}
        
        if board_type:
            params['type'] = board_type
        
        response = requests.get(url, headers=self.headers, auth=self.auth, params=params)
        
        if response.status_code != 200:
            print(f"警告: ボード情報の取得に失敗しました (ステータスコード: {response.status_code})")
            print(f"レスポンス: {response.text}")
            return []
        
        data = response.json()
        return data.get('values', [])
    
    def get_velocity_from_board(self, board_id: int) -> Dict:
        """
        ボードからベロシティ情報を取得
        
        Args:
            board_id: ボードID
            
        Returns:
            ベロシティ情報の辞書
        """
        # JIRA Agile API (greenhopper) を使用してベロシティチャートデータを取得
        url = f"{self.jira_url}/rest/greenhopper/1.0/rapid/charts/velocity"
        params = {'rapidViewId': board_id}
        
        response = requests.get(url, headers=self.headers, auth=self.auth, params=params)
        
        if response.status_code != 200:
            print(f"警告: ベロシティ情報の取得に失敗しました (ステータスコード: {response.status_code})")
            return {}
        
        return response.json()
    
    def get_sprints_from_board(self, board_id: int) -> List[Dict]:
        """
        ボードからスプリント情報を取得
        
        Args:
            board_id: ボードID
            
        Returns:
            スプリント情報のリスト
        """
        url = f"{self.jira_url}/rest/agile/1.0/board/{board_id}/sprint"
        params = {'state': 'closed'}  # 完了したスプリントのみ
        
        response = requests.get(url, headers=self.headers, auth=self.auth, params=params)
        
        if response.status_code != 200:
            return []
        
        data = response.json()
        return data.get('values', [])
    
    def calculate_average_velocity_from_api(self, project_key: str) -> Tuple[float, float]:
        """
        JIRA APIからベロシティの平均を計算
        
        Args:
            project_key: プロジェクトキー
            
        Returns:
            (平均ベロシティ（ストーリーポイント/スプリント）, 平均スプリント期間（日数）)
        """
        # まずスクラムボードを探す
        print(f"スクラムボードを検索中...")
        scrum_boards = self.get_boards_for_project(project_key, 'scrum')
        
        # スクラムボードが見つからない場合、全てのボードを取得
        if not scrum_boards:
            print(f"スクラムボードが見つかりませんでした。全てのボードを取得します...")
            all_boards = self.get_boards_for_project(project_key, None)
            
            if not all_boards:
                print(f"警告: プロジェクト {project_key} のボードが見つかりませんでした")
                return 0.0, 0.0
            
            # 全てのボードの情報を表示
            print(f"\n見つかったボード: {len(all_boards)}件")
            for i, board in enumerate(all_boards):
                print(f"  {i+1}. {board['name']} (ID: {board['id']}, タイプ: {board['type']})")
            
            # 全てのボードからベロシティを取得してみる
            boards = all_boards
        else:
            print(f"見つかったスクラムボード: {len(scrum_boards)}件")
            for i, board in enumerate(scrum_boards):
                print(f"  {i+1}. {board['name']} (ID: {board['id']})")
            boards = scrum_boards
        
        # 各ボードからベロシティを取得
        for board in boards:
            board_id = board['id']
            board_name = board['name']
            board_type = board.get('type', '不明')
            
            print(f"\nボードからベロシティを取得中: {board_name} (ID: {board_id}, タイプ: {board_type})")
            
            # ベロシティ情報を取得
            velocity_data = self.get_velocity_from_board(board_id)
            
            if not velocity_data:
                print(f"  → ベロシティデータが取得できませんでした（このボードにはベロシティがないかもしれません）")
                continue
            
            # ベロシティデータから完了したスプリントのデータを抽出
            velocities = []
            sprints = velocity_data.get('velocityStatEntries', {})
            
            if not sprints:
                print(f"  → スプリントデータがありません")
                continue
            
            for sprint_id, sprint_data in sprints.items():
                # completed が存在し、完了したスプリントのみを対象
                estimated = sprint_data.get('estimated', {})
                completed = estimated.get('value', 0)
                
                if completed > 0:
                    velocities.append(completed)
            
            if not velocities:
                print(f"  → 完了したスプリントのベロシティデータがありません")
                continue
            
            # ベロシティが取得できたので、このボードを使用
            avg_velocity = sum(velocities) / len(velocities)
            
            print(f"  ✓ 取得成功！")
            print(f"  取得したスプリント数: {len(velocities)}件")
            print(f"  各スプリントのベロシティ: {[f'{v:.1f}' for v in velocities]}")
            print(f"  平均ベロシティ: {avg_velocity:.2f} ポイント/スプリント")
            
            # スプリントの平均期間を計算
            sprints = self.get_sprints_from_board(board_id)
            sprint_durations = []
            
            for sprint in sprints:
                start_date_str = sprint.get('startDate')
                end_date_str = sprint.get('endDate')
                
                if start_date_str and end_date_str:
                    try:
                        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
                        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                        duration = (end_date - start_date).days
                        if duration > 0:
                            sprint_durations.append(duration)
                    except:
                        continue
            
            if sprint_durations:
                avg_sprint_duration = sum(sprint_durations) / len(sprint_durations)
                print(f"  平均スプリント期間: {avg_sprint_duration:.1f} 日")
            else:
                # デフォルトは2週間（14日）
                avg_sprint_duration = 14.0
                print(f"  スプリント期間が取得できませんでした。デフォルト値を使用: {avg_sprint_duration} 日")
            
            return avg_velocity, avg_sprint_duration
        
        print("\n警告: どのボードからもベロシティデータを取得できませんでした")
        return 0.0, 0.0
    
    def calculate_story_points_over_time(
        self,
        issues: List[Dict],
        start_date: datetime,
        end_date: datetime,
        interval_days: int = 7
    ) -> Tuple[List[str], List[float], List[float]]:
        """
        時系列でストーリーポイントを計算
        
        Args:
            issues: JIRA チケットのリスト
            start_date: 開始日時
            end_date: 終了日時
            interval_days: データポイント間の日数（デフォルト: 7日 = 1週間）
            
        Returns:
            (日付リスト, 全体のストーリーポイントリスト, 完了済みストーリーポイントリスト)
        """
        story_point_field = self.get_story_point_field_id()
        zakkuri_point_field = self.get_zakkuri_point_field_id()
        
        # 日付リストを生成
        dates = []
        current_date = start_date
        while current_date <= end_date:
            dates.append(current_date)
            current_date += timedelta(days=interval_days)
        
        total_points_over_time = []
        completed_points_over_time = []
        
        # 現在の日付を取得
        today = datetime.now().date()
        
        for date in dates:
            total_points = 0
            completed_points = 0
            
            # 未来の日付の場合、完了済みポイントは計算しない（後で最終値で埋める）
            is_future = date.date() > today
            
            for issue in issues:
                fields = issue.get('fields', {})
                
                # Story Point を取得（フォールバック付き）
                story_points = fields.get(story_point_field)
                
                # ステップ2: Story Point が None の場合、ざっくりポイントを使用
                if story_points is None and zakkuri_point_field:
                    story_points = fields.get(zakkuri_point_field)
                
                if story_points is None:
                    continue
                
                try:
                    story_points = float(story_points)
                except (ValueError, TypeError):
                    continue
                
                # チケットの作成日を確認
                created_str = fields.get('created')
                if not created_str:
                    continue
                
                created_date = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                
                # この日付時点でチケットが存在するか確認
                if created_date.date() <= date.date():
                    total_points += story_points
                    
                    # 未来の日付では完了済みポイントを計算しない
                    if not is_future:
                        # 完了済みかどうかを確認
                        status = fields.get('status', {}).get('name', '')
                        resolution_date_str = fields.get('resolutiondate')
                        
                        # 完了済みの判定（Done, Closed など）
                        completed_statuses = ['Done', 'Closed', 'Resolved', '完了', 'クローズ']
                        is_completed = status in completed_statuses
                        
                        # 解決日が設定されている場合はそれも考慮
                        if resolution_date_str:
                            resolution_date = datetime.fromisoformat(resolution_date_str.replace('Z', '+00:00'))
                            if resolution_date.date() <= date.date():
                                is_completed = True
                        
                        if is_completed:
                            completed_points += story_points
            
            total_points_over_time.append(total_points)
            completed_points_over_time.append(completed_points)
        
        # 未来の完了済みポイントを最後の実績値で埋める
        last_actual_completed = None
        for i in range(len(dates)):
            date = dates[i].date()
            if date <= today:
                last_actual_completed = completed_points_over_time[i]
            elif last_actual_completed is not None:
                # 未来の日付には最後の実績値を設定
                completed_points_over_time[i] = last_actual_completed
        
        # 日付を文字列に変換
        date_strings = [date.strftime('%Y-%m-%d') for date in dates]
        
        return date_strings, total_points_over_time, completed_points_over_time
    
    def calculate_burnup_data(
        self,
        total_points: List[float],
        completed_points: List[float]
    ) -> Tuple[List[float], List[float]]:
        """
        バーンアップチャート用のデータを計算
        
        Args:
            total_points: 全体のストーリーポイントリスト（スコープライン）
            completed_points: 完了済みストーリーポイントリスト
            
        Returns:
            (完了済みポイント, 全体のスコープポイント)
        """
        # バーンアップチャートでは完了済みポイントと全体のポイントをそのまま使用
        return completed_points, total_points
    
    def calculate_velocity_forecast(
        self,
        completed_points: List[float],
        num_points: int,
        target_value: float,
        interval_days: int,
        actual_data_length: int,
        api_avg_velocity: float = None,
        avg_sprint_duration: float = None,
        velocity_multiplier: float = 1.0
    ) -> Tuple[List[float], float]:
        """
        ベロシティベースの進捗予想ラインを生成
        
        Args:
            completed_points: 完了済みストーリーポイントのリスト（未来の期間を含む可能性あり）
            num_points: 総データポイント数
            target_value: 目標値（最終的な全体のストーリーポイント）
            interval_days: チャートのデータポイント間の日数
            actual_data_length: 実際のデータの長さ（未来の期間を除く）
            api_avg_velocity: JIRA APIから取得した平均ベロシティ（ポイント/スプリント）（オプション）
            avg_sprint_duration: 平均スプリント期間（日数）（オプション）
            
        Returns:
            (進捗予想のリスト, 使用した平均ベロシティ（チャート期間単位）)
        """
        if not completed_points or actual_data_length < 1:
            return [0] * num_points, 0.0
        
        # 実際のデータのみを使ってベロシティを計算
        actual_completed_points = completed_points[:actual_data_length]
        
        # 平均ベロシティを決定
        if api_avg_velocity is not None and api_avg_velocity > 0 and avg_sprint_duration is not None and avg_sprint_duration > 0:
            # API から取得したベロシティをチャートの期間単位に変換
            # ベロシティ/スプリント → ベロシティ/チャート期間
            base_velocity = api_avg_velocity * (interval_days / avg_sprint_duration)
            avg_velocity = base_velocity * velocity_multiplier
            
            print(f"\nJIRA APIから取得したベロシティを使用:")
            print(f"  スプリントベロシティ: {api_avg_velocity:.2f} ポイント/スプリント")
            print(f"  スプリント期間: {avg_sprint_duration:.1f} 日")
            print(f"  チャート期間: {interval_days} 日")
            print(f"  変換後のベロシティ: {base_velocity:.2f} ポイント/{interval_days}日間")
            if velocity_multiplier != 1.0:
                print(f"  調整後のベロシティ: {avg_velocity:.2f} ポイント/{interval_days}日間 (×{velocity_multiplier:.2f})")
        else:
            # 各期間のベロシティ（増分）を計算
            velocities = []
            for i in range(1, len(actual_completed_points)):
                velocity = actual_completed_points[i] - actual_completed_points[i-1]
                if velocity > 0:  # 正の増分のみを考慮
                    velocities.append(velocity)
            
            # 平均ベロシティを計算
            if not velocities:
                base_velocity = 0
            else:
                base_velocity = sum(velocities) / len(velocities)
            
            avg_velocity = base_velocity * velocity_multiplier
            
            print(f"\n完了データから計算したベロシティを使用:")
            print(f"  ベースベロシティ: {base_velocity:.2f} ポイント/{interval_days}日間")
            if velocity_multiplier != 1.0:
                print(f"  調整後のベロシティ: {avg_velocity:.2f} ポイント/{interval_days}日間 (×{velocity_multiplier:.2f})")
        
        # 進捗予想ラインを生成
        # 過去は実績値、未来は予測値
        forecast = []
        
        if actual_data_length <= 0:
            return [0] * num_points, avg_velocity
        
        if not actual_completed_points or len(actual_completed_points) == 0:
            return [0] * num_points, avg_velocity
        
        if actual_data_length > len(actual_completed_points):
            actual_data_length = len(actual_completed_points)
        
        last_actual_value = actual_completed_points[actual_data_length - 1]
        
        for i in range(num_points):
            if i < actual_data_length:
                # 過去：実績値をそのまま使用
                forecast.append(actual_completed_points[i])
            else:
                # 未来：最後の実績値からベロシティで予測
                periods_ahead = i - actual_data_length + 1
                predicted_value = last_actual_value + (avg_velocity * periods_ahead)
                forecast.append(predicted_value)
        
        return forecast, avg_velocity
    
    def generate_mermaid_chart(
        self,
        dates: List[str],
        total_scope: List[float],
        completed_points: List[float],
        velocity_forecast: List[float] = None,
        chart_title: str = "バーンアップチャート"
    ) -> str:
        """
        Mermaid XY Chart のコードを生成（バーンアップチャート）
        
        Args:
            dates: 日付リスト
            total_scope: 全体のスコープ（全ストーリーポイント）
            completed_points: 完了済みストーリーポイント
            velocity_forecast: ベロシティベースの進捗予想（オプション）
            chart_title: チャートタイトル
            
        Returns:
            Mermaid チャートのコード
        """
        # 最大値を計算（y軸の範囲設定用）
        max_value = max(
            max(total_scope) if total_scope else 0,
            max(completed_points) if completed_points else 0
        )
        if velocity_forecast:
            max_value = max(max_value, max(velocity_forecast) if velocity_forecast else 0)
        max_value = int(max_value) + 50  # 余裕を持たせる
        
        # 日付ラベルを簡潔にする（月/日 形式）
        date_labels = []
        for date_str in dates:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d')
            date_labels.append(date_obj.strftime('%m/%d'))
        
        # Mermaid コードを生成
        # 注: 各lineのラベルは自動的に凡例として表示されます
        mermaid_code = f'''%%{{init: {{'theme':'base'}}}}%%
xychart-beta
    title "{chart_title}"
    x-axis "日付" [{', '.join([f'"{label}"' for label in date_labels])}]
    y-axis "ストーリーポイント" 0 --> {max_value}
    line "全体のスコープ" [{', '.join([f'{v:.2f}' for v in total_scope])}]
    line "完了済み" [{', '.join([f'{v:.2f}' for v in completed_points])}]'''
        
        # 進捗予想ラインを追加（凡例に自動的に表示されます）
        if velocity_forecast:
            mermaid_code += f'''
    line "進捗予想（ベロシティ平均）" [{', '.join([f'{v:.2f}' for v in velocity_forecast])}]'''
        
        return mermaid_code


def main():
    """メイン処理"""
    # .env ファイルから環境変数を読み込む
    load_dotenv()
    
    # 環境変数から設定を読み込む
    jira_url = os.getenv('JIRA_URL')
    jira_username = os.getenv('JIRA_USERNAME')
    jira_api_token = os.getenv('JIRA_API_TOKEN')
    project_key = os.getenv('JIRA_PROJECT_KEY')
    version_name = os.getenv('JIRA_VERSION_NAME')
    
    # 必須パラメータのチェック
    if not all([jira_url, jira_username, jira_api_token, project_key, version_name]):
        print("エラー: 以下の環境変数を設定してください:")
        print("  JIRA_URL: JIRA インスタンスの URL (例: https://your-domain.atlassian.net)")
        print("  JIRA_USERNAME: JIRA ユーザー名（メールアドレス）")
        print("  JIRA_API_TOKEN: JIRA API トークン")
        print("  JIRA_PROJECT_KEY: プロジェクトキー (例: PROJ)")
        print("  JIRA_VERSION_NAME: バージョン名 (例: Release 1.0)")
        print("\nオプション:")
        print("  JIRA_STORY_POINT_FIELD: Story Point のカスタムフィールド ID (デフォルト: customfield_10016)")
        print("  JIRA_START_DATE: 開始日 (YYYY-MM-DD形式, デフォルト: 90日前)")
        print("  JIRA_END_DATE: 終了日 (YYYY-MM-DD形式, デフォルト: 今日)")
        print("  JIRA_INTERVAL_DAYS: データポイント間の日数 (デフォルト: 7)")
        sys.exit(1)
    
    # オプションパラメータ
    start_date_str = os.getenv('JIRA_START_DATE')
    end_date_str = os.getenv('JIRA_END_DATE')
    interval_days = int(os.getenv('JIRA_INTERVAL_DAYS', '7'))
    
    # 日付の設定
    if start_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=90)
    
    if end_date_str:
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    # チャート生成器を初期化
    generator = JiraMermaidChartGenerator(jira_url, jira_username, jira_api_token)
    
    print(f"JIRA からデータを取得中...")
    print(f"  プロジェクト: {project_key}")
    print(f"  バージョン: {version_name}")
    
    # チケット一覧を取得
    issues = generator.get_issues_by_version(project_key, version_name)
    print(f"  取得チケット数: {len(issues)}")
    
    if not issues:
        print("警告: チケットが見つかりませんでした。")
        print("プロジェクトキーとバージョン名を確認してください。")
        sys.exit(1)
    
    # デバッグ: 最初のチケットのフィールド情報を表示
    if issues:
        print("\n" + "="*80)
        print("【ステップ1】デバッグ情報: フィールド一覧")
        print("="*80)
        
        # すべてのフィールド定義を取得
        print("フィールド定義を取得中...")
        all_field_defs = generator.get_all_fields()
        
        first_issue = issues[0]
        fields = first_issue.get('fields', {})
        
        # Story Point 関連のカスタムフィールドを探す
        story_point_field = generator.get_story_point_field_id()
        print(f"\n設定されているストーリーポイントフィールド: {story_point_field}")
        print(f"その値: {fields.get(story_point_field)}")
        
        print("\nすべてのカスタムフィールド（フィールド名付き）:")
        for key, value in sorted(fields.items()):
            if key.startswith('customfield_'):
                field_name = all_field_defs.get(key, '不明')
                # 値が設定されているもののみ表示
                if value is not None:
                    print(f"  {key}: {field_name} = {value}")
        
        # 「ざっくりポイント」を探す
        print("\n「ざっくりポイント」フィールドを探しています...")
        zakkuri_field_found = None
        for field_id, field_name in all_field_defs.items():
            if 'ざっくりポイント' in field_name or 'ざっくり' in field_name:
                print(f"  ✓ 見つかりました: {field_id} = {field_name}")
                zakkuri_field_found = field_id
                if field_id in fields:
                    print(f"    最初のチケットでの値: {fields[field_id]}")
        
        if not zakkuri_field_found:
            print("  ✗ 「ざっくりポイント」フィールドが見つかりませんでした")
            print("  ヒント: 上記のカスタムフィールド一覧から手動で確認してください")
        
        print("="*80 + "\n")
    
    # 時系列でストーリーポイントを計算
    dates, total_points, completed_points = generator.calculate_story_points_over_time(
        issues, start_date, end_date, interval_days
    )
    
    
    # バーンアップチャート用のデータを計算
    completed_data, scope_data = generator.calculate_burnup_data(
        total_points, completed_points
    )
    
    # 実際のデータの長さを保持（今日までのデータポイント数）
    # プログラム実行日時より先の日付は全て未来
    today = datetime.now().date()
    actual_data_length = 0
    for date_str in dates:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if date <= today:
            actual_data_length += 1
        else:
            break
    
    # 現在の進捗を表示
    if scope_data and completed_data:
        current_scope = scope_data[-1]
        current_completed = completed_data[actual_data_length - 1] if actual_data_length > 0 else 0
        progress = (current_completed / current_scope * 100) if current_scope > 0 else 0
        print(f"\n現在の進捗: {current_completed:.1f} / {current_scope:.1f} ポイント ({progress:.1f}%)")
    
    # 目標値を設定（最終スコープ）
    target_value = scope_data[-1] if scope_data else 0
    
    # JIRA APIからベロシティを取得
    print("\n" + "="*80)
    print("JIRA APIからベロシティ情報を取得中...")
    print("="*80)
    api_avg_velocity, avg_sprint_duration = generator.calculate_average_velocity_from_api(project_key)
    
    # ベロシティ調整係数を取得（環境変数）
    velocity_adjustment = float(os.getenv('JIRA_VELOCITY_ADJUSTMENT', '100'))
    velocity_multiplier = velocity_adjustment / 100.0
    
    if velocity_adjustment != 100:
        print(f"\nベロシティ調整: {velocity_adjustment}% (係数: {velocity_multiplier:.2f})")
    
    # ベロシティを取得して、未来の期間を追加
    if api_avg_velocity > 0 and avg_sprint_duration > 0:
        # APIから取得したベロシティをチャート期間単位に変換
        chart_velocity = api_avg_velocity * (interval_days / avg_sprint_duration)
        # 調整係数を適用
        chart_velocity = chart_velocity * velocity_multiplier
    else:
        # 完了データから計算
        temp_velocities = []
        if len(completed_data) >= 2:
            for i in range(1, len(completed_data)):
                v = completed_data[i] - completed_data[i-1]
                if v > 0:
                    temp_velocities.append(v)
        chart_velocity = sum(temp_velocities) / len(temp_velocities) if temp_velocities else 0
        # 調整係数を適用
        chart_velocity = chart_velocity * velocity_multiplier
    
    # 進捗予想ラインが目標値に達するまでの期間を計算して追加
    # target_valueが0の場合でも最低限の未来期間を追加
    if chart_velocity > 0:
        if target_value > 0:
            # 進捗予想ラインが目標値に達するまでの期間
            # 現在の完了値から目標値までの残りを計算
            current_completed = completed_data[actual_data_length - 1] if actual_data_length > 0 else 0
            remaining = target_value - current_completed
            if remaining > 0:
                periods_to_complete = int(remaining / chart_velocity) + 1
                periods_to_target = actual_data_length + periods_to_complete + 2  # 余裕を持って+2
            else:
                periods_to_target = actual_data_length + 5  # 最低5期間追加
        else:
            # target_valueが0の場合は、デフォルトで5期間追加
            periods_to_target = len(dates) + 5
        
        current_periods = len(dates)
        
        # 現在の期間数が不足している場合、未来の期間を追加
        if periods_to_target > current_periods:
            periods_to_add = periods_to_target - current_periods
            last_date = datetime.strptime(dates[-1], '%Y-%m-%d')
            
            for i in range(1, periods_to_add + 1):
                future_date = last_date + timedelta(days=interval_days * i)
                dates.append(future_date.strftime('%Y-%m-%d'))
                scope_data.append(scope_data[-1] if scope_data else 0)
                completed_data.append(completed_data[-1] if completed_data else 0)
            
            print(f"\n未来の期間を {periods_to_add} 期間追加しました")
    
    # ベロシティベースの進捗予想を計算
    velocity_forecast, avg_velocity = generator.calculate_velocity_forecast(
        completed_data, len(dates), target_value, interval_days, actual_data_length,
        api_avg_velocity, avg_sprint_duration, velocity_multiplier
    )
    
    # 予想完了時期を計算
    if avg_velocity > 0:
        # 実際のデータの最後の値を使用
        actual_completed = completed_data[actual_data_length - 1] if actual_data_length > 0 else 0
        remaining = target_value - actual_completed
        if remaining > 0:
            periods_needed = remaining / avg_velocity
            days_needed = periods_needed * interval_days
            
            print(f"\n残りポイント: {remaining:.2f}")
            print(f"予想完了まで: {periods_needed:.1f} 期間（約 {days_needed:.0f} 日）")
            
            # 予想完了日を計算（今日を基準にする）
            today = datetime.now()
            estimated_completion_date = today + timedelta(days=days_needed)
            print(f"予想完了日: {estimated_completion_date.strftime('%Y年%m月%d日')} (今日 {today.strftime('%Y年%m月%d日')} から計算)")
        else:
            print(f"\n✓ すでに完了しています！")
    print("="*80)
    
    # Mermaid チャートコードを生成
    mermaid_code = generator.generate_mermaid_chart(
        dates, scope_data, completed_data, velocity_forecast
    )
    
    print("\n" + "="*80)
    print("生成された Mermaid チャートコード:")
    print("="*80)
    print(mermaid_code)
    print("="*80)
    
    # ファイルに出力
    output_file = 'mermaid_chart.txt'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(mermaid_code)
    
    print(f"\nチャートコードを {output_file} に保存しました。")
    print("\nNotion での使い方:")
    print("1. Notion ページで /code と入力")
    print("2. 言語として 'Mermaid' を選択")
    print("3. 上記のコードを貼り付け")


if __name__ == '__main__':
    main()

