from app.domain.creation import SkillDescriptor


class MonthlyOutfitAdvisorSkill:
    descriptor = SkillDescriptor(
        skill_id="monthly-outfit-advisor",
        name="\u672c\u6708\u7a7f\u642d\u5efa\u8bae Skill",
        description=(
            "\u6839\u636e\u6708\u4efd\u3001"
            "\u5b63\u8282\u548c\u573a\u666f"
            "\u8f93\u51fa\u7a7f\u642d\u5efa\u8bae\u3002"
        ),
        version="1.0.0",
        required_capabilities=[],
    )
