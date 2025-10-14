"""
WarmupMonitor - мониторинг и метрики системы прогрева
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from database import (
    get_all_accounts,
    get_account_by_id,
    get_persona,
    get_warmup_sessions,
    get_relevant_chats
)

logger = logging.getLogger(__name__)


class WarmupMonitor:
    """
    Мониторинг и метрики системы прогрева аккаунтов
    """
    
    def get_daily_report(self) -> Dict[str, Any]:
        """
        Ежедневный отчет
        
        Returns:
            Dict с метриками за последние 24 часа
        """
        
        logger.info("Generating daily report...")
        
        cutoff_time = datetime.utcnow() - timedelta(days=1)
        
        # Получить все аккаунты
        all_accounts = get_all_accounts(limit=1000)
        
        warmed_today = 0
        total_actions_today = 0
        total_successful = 0
        total_failed = 0
        floodwait_count = 0
        
        for account in all_accounts:
            last_warmup = account.get("last_warmup_date")
            if last_warmup:
                try:
                    last_time = datetime.fromisoformat(last_warmup)
                    if last_time >= cutoff_time:
                        warmed_today += 1
                        
                        # Get sessions for this account
                        sessions = get_warmup_sessions(account["id"], limit=5)
                        for session in sessions:
                            started = session.get("started_at")
                            if started:
                                try:
                                    session_time = datetime.fromisoformat(started)
                                    if session_time >= cutoff_time:
                                        total_actions_today += session.get("completed_actions_count", 0)
                                        total_successful += session.get("completed_actions_count", 0)
                                        total_failed += session.get("failed_actions_count", 0)
                                except:
                                    pass
                except:
                    pass
            
            # Check for frozen accounts (FloodWait)
            if account.get("is_frozen"):
                floodwait_count += 1
        
        success_rate = 0
        if total_successful + total_failed > 0:
            success_rate = (total_successful / (total_successful + total_failed)) * 100
        
        # Top active accounts
        active_accounts = sorted(
            [acc for acc in all_accounts if acc.get("total_warmups", 0) > 0],
            key=lambda x: x.get("total_warmups", 0),
            reverse=True
        )[:5]
        
        top_active = []
        for acc in active_accounts:
            persona = get_persona(acc["id"])
            top_active.append({
                "session_id": acc["session_id"][:8] + "...",
                "phone": acc["phone_number"][-4:] + "****",
                "name": persona.get("generated_name") if persona else "Unknown",
                "total_warmups": acc.get("total_warmups", 0),
                "total_actions": acc.get("total_actions", 0),
                "stage": acc.get("warmup_stage", 1)
            })
        
        report = {
            "date": datetime.utcnow().date().isoformat(),
            "accounts_warmed_today": warmed_today,
            "total_actions_today": total_actions_today,
            "successful_actions": total_successful,
            "failed_actions": total_failed,
            "success_rate": round(success_rate, 2),
            "floodwait_accounts": floodwait_count,
            "top_active_accounts": top_active,
            "total_accounts": len(all_accounts),
            "active_accounts": len([a for a in all_accounts if a.get("is_active")]),
            "frozen_accounts": len([a for a in all_accounts if a.get("is_frozen")]),
            "banned_accounts": len([a for a in all_accounts if a.get("is_banned")])
        }
        
        logger.info(f"Daily report generated: {report}")
        return report
    
    def check_account_health(self, account_id: int) -> Dict[str, Any]:
        """
        Проверка здоровья аккаунта
        
        Args:
            account_id: ID аккаунта
            
        Returns:
            Dict с оценкой здоровья и рекомендациями
        """
        
        account = get_account_by_id(account_id)
        if not account:
            return {"error": "Account not found"}
        
        # Получить последние сессии
        sessions = get_warmup_sessions(account_id, limit=10)
        
        health_score = 100.0
        issues = []
        recommendations = []
        
        # Проверка 1: Частота ошибок
        if sessions:
            total_actions = sum(s.get("planned_actions_count", 0) for s in sessions)
            failed_actions = sum(s.get("failed_actions_count", 0) for s in sessions)
            
            if total_actions > 0:
                error_rate = (failed_actions / total_actions) * 100
                if error_rate > 30:
                    health_score -= 30
                    issues.append(f"High error rate: {error_rate:.1f}%")
                    recommendations.append("Reduce activity frequency or check account status")
                elif error_rate > 15:
                    health_score -= 15
                    issues.append(f"Moderate error rate: {error_rate:.1f}%")
        
        # Проверка 2: FloodWait или заморозка
        if account.get("is_frozen"):
            health_score -= 50
            issues.append("Account is frozen (FloodWait detected)")
            recommendations.append("Wait 24-48 hours before resuming activity")
        
        if account.get("is_banned"):
            health_score = 0
            issues.append("Account is banned")
            recommendations.append("Account needs manual review")
        
        # Проверка 3: Активность соответствует стадии
        stage = account.get("warmup_stage", 1)
        total_warmups = account.get("total_warmups", 0)
        
        # Ожидаемое количество прогревов на текущей стадии
        expected_min = (stage - 1) * 2  # Минимум 2 раза в день
        if total_warmups < expected_min:
            health_score -= 10
            issues.append("Low activity for current stage")
            recommendations.append("Increase daily activity count")
        
        # Проверка 4: Есть ли личность
        persona = get_persona(account_id)
        if not persona:
            health_score -= 10
            issues.append("No persona configured")
            recommendations.append("Generate persona for more natural behavior")
        
        # Проверка 5: Есть ли релевантные чаты
        chats = get_relevant_chats(account_id, limit=10)
        if len(chats) < 3:
            health_score -= 5
            issues.append("Few relevant chats discovered")
            recommendations.append("Run chat discovery to find more relevant channels")
        
        # Определить статус здоровья
        if health_score >= 80:
            health_status = "excellent"
        elif health_score >= 60:
            health_status = "good"
        elif health_score >= 40:
            health_status = "fair"
        elif health_score >= 20:
            health_status = "poor"
        else:
            health_status = "critical"
        
        return {
            "account_id": account_id,
            "session_id": account["session_id"][:8] + "...",
            "health_score": round(health_score, 2),
            "health_status": health_status,
            "issues": issues,
            "recommendations": recommendations,
            "statistics": {
                "warmup_stage": stage,
                "total_warmups": total_warmups,
                "total_actions": account.get("total_actions", 0),
                "joined_channels": account.get("joined_channels_count", 0),
                "sent_messages": account.get("sent_messages_count", 0),
                "last_warmup": account.get("last_warmup_date"),
                "is_active": account.get("is_active", False),
                "is_frozen": account.get("is_frozen", False),
                "is_banned": account.get("is_banned", False)
            }
        }
    
    def get_statistics_summary(self) -> Dict[str, Any]:
        """
        Получить общую статистику системы
        
        Returns:
            Dict с общими метриками
        """
        
        all_accounts = get_all_accounts(limit=1000)
        
        if not all_accounts:
            return {
                "total_accounts": 0,
                "active_accounts": 0,
                "average_stage": 0,
                "message": "No accounts in system"
            }
        
        active = [a for a in all_accounts if a.get("is_active")]
        frozen = [a for a in all_accounts if a.get("is_frozen")]
        banned = [a for a in all_accounts if a.get("is_banned")]
        
        # Средняя стадия прогрева
        stages = [a.get("warmup_stage", 1) for a in active]
        avg_stage = sum(stages) / len(stages) if stages else 0
        
        # Общее количество действий
        total_actions = sum(a.get("total_actions", 0) for a in all_accounts)
        total_warmups = sum(a.get("total_warmups", 0) for a in all_accounts)
        
        return {
            "total_accounts": len(all_accounts),
            "active_accounts": len(active),
            "frozen_accounts": len(frozen),
            "banned_accounts": len(banned),
            "average_warmup_stage": round(avg_stage, 2),
            "total_warmups_all_time": total_warmups,
            "total_actions_all_time": total_actions,
            "accounts_by_stage": self._get_accounts_by_stage(all_accounts)
        }
    
    def _get_accounts_by_stage(self, accounts: List[Dict[str, Any]]) -> Dict[str, int]:
        """Подсчет аккаунтов по стадиям"""
        
        by_stage = {}
        for account in accounts:
            stage = account.get("warmup_stage", 1)
            by_stage[f"stage_{stage}"] = by_stage.get(f"stage_{stage}", 0) + 1
        
        return by_stage

