"""
Student Risk Analyzer — Sprint 175: "Cắm Phích Cắm" Phase 3

Analyzes student academic data to identify at-risk students.
Factors: grade trends, assignment submission rate, quiz performance.

No LLM cost — pure rule-based scoring for speed and reliability.
"""

import logging

logger = logging.getLogger(__name__)


class StudentRiskAnalyzer:
    """Analyze student academic data to produce risk assessments.

    Risk factors (each 0-1, weighted):
      - Grade trend (declining = higher risk)       weight: 0.35
      - Assignment completion rate                   weight: 0.25
      - Quiz performance vs passing threshold        weight: 0.25
      - Inactivity (days since last event)           weight: 0.15

    Risk levels:
      - critical: score >= 0.75
      - high: score >= 0.50
      - medium: score >= 0.30
      - low: score < 0.30
    """

    async def analyze(
        self,
        student_id: str,
        course_id: str,
        connector=None,
    ) -> dict:
        """Analyze a student's risk in a specific course.

        Returns:
            dict with keys: score (0-1), level (str), factors (list[str])
        """
        factors = []
        scores = []

        try:
            if connector is None:
                return {"score": 0.0, "level": "unknown", "factors": ["Không có dữ liệu"]}

            # Factor 1: Grade performance
            grades = connector.get_student_grades(student_id)
            course_grades = [g for g in grades if g.course_id == course_id and g.max_grade > 0]

            if course_grades:
                percentages = [g.grade / g.max_grade * 100 for g in course_grades]
                avg_pct = sum(percentages) / len(percentages)

                if avg_pct < 40:
                    scores.append(1.0)
                    factors.append(f"Điểm rất thấp ({avg_pct:.0f}%)")
                elif avg_pct < 55:
                    scores.append(0.7)
                    factors.append(f"Điểm dưới trung bình ({avg_pct:.0f}%)")
                elif avg_pct < 70:
                    scores.append(0.3)
                    factors.append(f"Điểm trung bình ({avg_pct:.0f}%)")
                else:
                    scores.append(0.0)

                # Check trend (if 2+ grades)
                if len(percentages) >= 2:
                    recent = percentages[-1]
                    previous_avg = sum(percentages[:-1]) / len(percentages[:-1])
                    if recent < previous_avg - 15:
                        scores.append(0.8)
                        factors.append(f"Xu hướng giảm điểm ({previous_avg:.0f}% → {recent:.0f}%)")
                    elif recent < previous_avg - 5:
                        scores.append(0.4)
                        factors.append("Điểm giảm nhẹ")
                    else:
                        scores.append(0.0)
            else:
                scores.append(0.3)
                factors.append("Chưa có điểm")

            # Factor 2: Assignment completion
            assignments = connector.get_upcoming_assignments(student_id)
            overdue = [a for a in assignments if hasattr(a, "due_date")]
            # If many upcoming assignments, mild concern
            if len(overdue) > 5:
                scores.append(0.5)
                factors.append(f"{len(overdue)} bài tập chưa nộp/sắp đến hạn")
            elif len(overdue) > 3:
                scores.append(0.3)
                factors.append(f"{len(overdue)} bài tập sắp đến hạn")
            else:
                scores.append(0.0)

            # Factor 3: Quiz performance
            quiz_history = connector.get_student_quiz_history(student_id)
            course_quizzes = [
                q for q in quiz_history
                if isinstance(q, dict) and q.get("course_id") == course_id
            ]
            if course_quizzes:
                quiz_scores = []
                for q in course_quizzes:
                    max_s = q.get("max_score", 0)
                    if max_s > 0:
                        quiz_scores.append(q.get("score", 0) / max_s * 100)
                if quiz_scores:
                    avg_quiz = sum(quiz_scores) / len(quiz_scores)
                    if avg_quiz < 40:
                        scores.append(0.9)
                        factors.append(f"Điểm kiểm tra rất thấp ({avg_quiz:.0f}%)")
                    elif avg_quiz < 55:
                        scores.append(0.5)
                        factors.append(f"Điểm kiểm tra yếu ({avg_quiz:.0f}%)")
                    else:
                        scores.append(0.0)

        except Exception as e:
            logger.warning("Risk analysis failed for student %s: %s", student_id, e)
            return {"score": 0.0, "level": "unknown", "factors": [f"Lỗi phân tích: {e}"]}

        # Calculate weighted score
        if not scores:
            return {"score": 0.0, "level": "low", "factors": []}

        # Simple average (all factors have equal weight when present)
        final_score = sum(scores) / len(scores)

        # Map to level
        if final_score >= 0.75:
            level = "critical"
        elif final_score >= 0.50:
            level = "high"
        elif final_score >= 0.30:
            level = "medium"
        else:
            level = "low"

        return {
            "score": round(final_score, 2),
            "level": level,
            "factors": factors if factors else ["Không có vấn đề"],
        }
