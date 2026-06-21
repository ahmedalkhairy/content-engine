"""Database seeding utilities."""

from sqlalchemy.orm import Session

from app.models import ContentCategory, ContentIdea, Project
from app.services.project_service import ensure_default_project

INFRAPILOT_CATEGORIES = [
    "Server Security",
    "SSH Exposure",
    "Outbound-only Agents",
    "Server Monitoring",
    "DevOps Mistakes",
    "Incident Response",
    "Linux Server Management",
    "Infrastructure Automation",
    "SaaS Operations",
    "Startup Infrastructure",
    "Alerts and Downtime",
    "Cloud Cost and Reliability",
    "Agent-based Management",
    "Access Control",
    "Infrastructure Visibility",
]

INFRAPILOT_IDEAS = [
    {
        "title": "What if you could manage servers without exposing SSH?",
        "topic": "SSH Exposure",
        "angle": "Security-first server management",
        "target_audience": "DevOps engineers, CTOs",
        "platform_preference": "both",
        "priority": 9,
    },
    {
        "title": "Why public SSH is still a common infrastructure risk",
        "topic": "SSH Exposure",
        "angle": "Common mistakes in server access",
        "target_audience": "System administrators",
        "platform_preference": "linkedin",
        "priority": 8,
    },
    {
        "title": "The difference between monitoring and operational visibility",
        "topic": "Infrastructure Visibility",
        "angle": "Beyond basic dashboards",
        "target_audience": "SREs, DevOps leads",
        "platform_preference": "linkedin",
        "priority": 8,
    },
    {
        "title": "Why small SaaS teams need simpler infrastructure management",
        "topic": "SaaS Operations",
        "angle": "Startup infrastructure challenges",
        "target_audience": "SaaS founders",
        "platform_preference": "both",
        "priority": 7,
    },
    {
        "title": "How outbound-only agents reduce attack surface",
        "topic": "Outbound-only Agents",
        "angle": "Security architecture",
        "target_audience": "Security-conscious DevOps",
        "platform_preference": "both",
        "priority": 9,
    },
    {
        "title": "Why server identity should be revocable",
        "topic": "Access Control",
        "angle": "Per-server identity model",
        "target_audience": "CTOs, security teams",
        "platform_preference": "linkedin",
        "priority": 8,
    },
    {
        "title": "The problem with shared server passwords",
        "topic": "Access Control",
        "angle": "Operational security risks",
        "target_audience": "System administrators",
        "platform_preference": "both",
        "priority": 7,
    },
    {
        "title": "What happens when a server silently goes offline?",
        "topic": "Alerts and Downtime",
        "angle": "Silent failures and detection",
        "target_audience": "SREs, hosting companies",
        "platform_preference": "both",
        "priority": 8,
    },
    {
        "title": "Why dashboards are not enough without automation",
        "topic": "Infrastructure Automation",
        "angle": "From visibility to action",
        "target_audience": "DevOps engineers",
        "platform_preference": "linkedin",
        "priority": 7,
    },
    {
        "title": "From monitoring to action: the future of server operations",
        "topic": "Server Monitoring",
        "angle": "Evolution of server management",
        "target_audience": "CTOs, DevOps leads",
        "platform_preference": "both",
        "priority": 6,
    },
]

GENERIC_CATEGORIES = [
    "Product Updates",
    "Industry Insights",
    "How-To Guides",
    "Customer Stories",
    "Company News",
]

GENERIC_IDEAS = [
    {
        "title": "What's the biggest challenge your team faces today?",
        "topic": "Industry Insights",
        "angle": "Audience engagement",
        "target_audience": "Professionals in your industry",
        "platform_preference": "both",
        "priority": 5,
    },
    {
        "title": "Three lessons we learned building our product",
        "topic": "Company News",
        "angle": "Founder perspective",
        "target_audience": "Entrepreneurs and product teams",
        "platform_preference": "linkedin",
        "priority": 6,
    },
]


def seed_database(db: Session, project: Project | None = None) -> dict:
    project = project or ensure_default_project(db)
    stats = {"categories": 0, "ideas": 0, "project": project.name}

    if project.slug == "infrapilot":
        categories = INFRAPILOT_CATEGORIES
        ideas = INFRAPILOT_IDEAS
    else:
        categories = GENERIC_CATEGORIES
        ideas = GENERIC_IDEAS

    category_map = {}
    for name in categories:
        existing = (
            db.query(ContentCategory)
            .filter(ContentCategory.project_id == project.id, ContentCategory.name == name)
            .first()
        )
        if not existing:
            cat = ContentCategory(project_id=project.id, name=name)
            db.add(cat)
            db.flush()
            category_map[name] = cat.id
            stats["categories"] += 1
        else:
            category_map[name] = existing.id

    for idea_data in ideas:
        existing = (
            db.query(ContentIdea)
            .filter(ContentIdea.project_id == project.id, ContentIdea.title == idea_data["title"])
            .first()
        )
        if existing:
            continue

        topic = idea_data.get("topic", "")
        idea = ContentIdea(
            project_id=project.id,
            title=idea_data["title"],
            topic=topic,
            angle=idea_data.get("angle", ""),
            target_audience=idea_data.get("target_audience", project.default_target_audience),
            platform_preference=idea_data.get("platform_preference", "both"),
            priority=idea_data.get("priority", 5),
            status="new",
            category_id=category_map.get(topic),
        )
        db.add(idea)
        stats["ideas"] += 1

    db.commit()
    return stats
