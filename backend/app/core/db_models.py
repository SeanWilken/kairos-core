from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BootstrapSessionModel(Base):
    __tablename__ = "bootstrap_sessions"

    session_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    runtime_json: Mapped[str] = mapped_column(Text, nullable=False)
    database_json: Mapped[str] = mapped_column(Text, nullable=False)
    deployment_json: Mapped[str] = mapped_column(Text, nullable=False)
    secrets_json: Mapped[str] = mapped_column(Text, nullable=False)
    vector_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class TenantModel(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class RuntimeCheckRunModel(Base):
    __tablename__ = "runtime_check_runs"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("bootstrap_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checks_json: Mapped[str] = mapped_column(Text, nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class IngestJobModel(Base):
    __tablename__ = "ingest_jobs"

    job_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("bootstrap_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source_files_json: Mapped[str] = mapped_column(Text, nullable=False)
    chunking_profile: Mapped[str] = mapped_column(Text, nullable=False)
    embedding_profile: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, nullable=False)
    error_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class StudioUserModel(Base):
    __tablename__ = "studio_users"

    user_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str] = mapped_column(Text, nullable=False, default="")
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    is_global_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_studio_users_tenant_email"),)


class StudioOrganizationModel(Base):
    __tablename__ = "studio_organizations"

    org_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="team")
    owner_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("studio_users.user_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_studio_organizations_tenant_slug"),
    )


class StudioOrganizationMembershipModel(Base):
    __tablename__ = "studio_org_memberships"

    membership_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", name="uq_studio_org_memberships_org_user"),
    )


class StudioUserCredentialModel(Base):
    __tablename__ = "studio_user_credentials"

    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )


class AuthRefreshTokenModel(Base):
    __tablename__ = "auth_refresh_tokens"

    token_id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    __table_args__ = (UniqueConstraint("token_hash", name="uq_auth_refresh_tokens_hash"),)


class StudioDivisionModel(Base):
    __tablename__ = "studio_divisions"

    division_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_studio_divisions_org_slug"),
    )


class StudioTeamModel(Base):
    __tablename__ = "studio_teams"

    team_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    division_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_divisions.division_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_team_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_teams.team_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    access_mode: Mapped[str] = mapped_column(Text, nullable=False, default="internal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_studio_teams_org_slug"),
    )


class StudioTeamMembershipModel(Base):
    __tablename__ = "studio_team_memberships"

    team_membership_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_teams.team_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_studio_team_memberships_team_user"),
    )


class StudioChannelModel(Base):
    __tablename__ = "studio_channels"

    channel_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_teams.team_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)
    response_policy: Mapped[str] = mapped_column(Text, nullable=False, default="single_best")
    auto_respond: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    responder_delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=12)
    default_persona_id: Mapped[str] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class StudioChannelParticipantModel(Base):
    __tablename__ = "studio_channel_participants"

    participant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_studio_channel_participants_channel_user"),
    )


class StudioChannelMessageModel(Base):
    __tablename__ = "studio_channel_messages"

    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class StudioPersonaModel(Base):
    __tablename__ = "studio_personas"

    persona_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="organization")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    model_profile: Mapped[str] = mapped_column(Text, nullable=False, default="reasoning-optimized")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    persona_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    approval_status: Mapped[str] = mapped_column(Text, nullable=False, default="draft")
    approved_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_studio_personas_org_slug"),
    )


class StudioTaskModel(Base):
    __tablename__ = "studio_tasks"

    task_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_teams.team_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="todo")
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="team_public")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    related_node_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    channel_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    owner_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class StudioTaskAssignmentModel(Base):
    __tablename__ = "studio_task_assignments"

    assignment_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_tasks.task_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assignee_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("task_id", "assignee_user_id", name="uq_studio_task_assignments_task_user"),
    )


class StudioMeetingModel(Base):
    __tablename__ = "studio_meetings"

    meeting_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    team_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_teams.team_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    channel_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="scheduled")
    scheduled_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default="UTC")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    agenda_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class StudioMeetingParticipantModel(Base):
    __tablename__ = "studio_meeting_participants"

    participant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    meeting_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_meetings.meeting_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False, default="attendee")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="invited")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("meeting_id", "user_id", name="uq_studio_meeting_participants_meeting_user"),
    )


class PersonaTemplateCategoryModel(Base):
    __tablename__ = "persona_template_categories"

    category_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_persona_template_categories_tenant_name"),)


class PersonaTemplateOptionModel(Base):
    __tablename__ = "persona_template_options"

    option_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    category_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("persona_template_categories.category_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    verbose_statement: Mapped[str] = mapped_column(Text, nullable=False)
    provider_compatibility_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("category_id", "key", name="uq_persona_template_options_category_key"),
    )


class PromptPrefabModel(Base):
    __tablename__ = "prompt_prefabs"

    prefab_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    industry: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    segment_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    tokens_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "industry",
            "role",
            "segment_type",
            "version",
            name="uq_prompt_prefabs_tenant_industry_role_segment",
        ),
    )


class PromptCatalogBundleModel(Base):
    __tablename__ = "prompt_catalog_bundles"

    bundle_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    bundle_version: Mapped[str] = mapped_column(Text, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    signature_alg: Mapped[str] = mapped_column(Text, nullable=False, default="")
    signature_key_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    signature_value: Mapped[str] = mapped_column(Text, nullable=False, default="")
    imported_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "bundle_id", name="uq_prompt_catalog_bundles_tenant_bundle"),
    )


class PersonaVersionModel(Base):
    __tablename__ = "persona_versions"

    version_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    persona_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_personas.persona_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_major: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    version_minor: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version_patch: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version_string: Mapped[str] = mapped_column(Text, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    generated_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    change_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "persona_id",
            "version_major",
            "version_minor",
            "version_patch",
            name="uq_persona_versions_persona_version",
        ),
    )


class PersonaVersionHistoryModel(Base):
    __tablename__ = "persona_version_history"

    history_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("persona_versions.version_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    old_value: Mapped[str] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=True)
    changed_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class UserPersonaContextModel(Base):
    __tablename__ = "user_persona_contexts"

    context_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    persona_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_personas.persona_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_strengths_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    user_weaknesses_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    autonomy_level: Mapped[str] = mapped_column(Text, nullable=False, default="moderate")
    communication_preference: Mapped[str] = mapped_column(Text, nullable=False, default="balanced")
    detail_level: Mapped[str] = mapped_column(Text, nullable=False, default="standard")
    check_in_frequency: Mapped[str] = mapped_column(Text, nullable=False, default="as_needed")
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("user_id", "persona_id", name="uq_user_persona_contexts_user_persona"),
    )


class RoomCouncilConfigModel(Base):
    __tablename__ = "room_council_config"

    config_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    council_head_persona_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_personas.persona_id", ondelete="SET NULL"),
        nullable=True,
    )
    council_mode: Mapped[str] = mapped_column(Text, nullable=False, default="summarized")
    delay_before_orchestration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=10000)
    show_reasoning_metadata: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_parallel_responses: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (UniqueConstraint("room_id", name="uq_room_council_config_room"),)


class RoomPersonaModel(Base):
    __tablename__ = "room_personas"

    room_persona_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    persona_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_personas.persona_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_in_room: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (UniqueConstraint("room_id", "persona_id", name="uq_room_personas_room_persona"),)


class PackImportQueueModel(Base):
    __tablename__ = "pack_import_queue"

    queue_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    pack_data_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    extracted_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    safety_flags_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending_review")
    review_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    installed_persona_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_personas.persona_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PackReviewConversationModel(Base):
    __tablename__ = "pack_review_conversations"

    conversation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    queue_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("pack_import_queue.queue_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    test_case_key: Mapped[str] = mapped_column(Text, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    response: Mapped[str] = mapped_column(Text, nullable=False, default="")
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("queue_id", "test_case_key", name="uq_pack_review_conversations_queue_case"),
    )


class ConversationOrchestrationRunModel(Base):
    __tablename__ = "conversation_orchestration_runs"

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    triggering_message_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channel_messages.message_id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_run_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_orchestration_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    )
    source_run_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_orchestration_runs.run_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    orchestration_type: Mapped[str] = mapped_column(Text, nullable=False, default="single_best")
    mode: Mapped[str] = mapped_column(Text, nullable=False, default="single_best")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued", index=True)
    client_message_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    total_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EventOutboxModel(Base):
    __tablename__ = "event_outbox"

    outbox_event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    orchestration_run_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("conversation_orchestration_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "room_id", "sequence", name="uq_event_outbox_tenant_room_sequence"),
    )


class AuditEventModel(Base):
    __tablename__ = "audit_events"

    audit_event_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False, default="system")
    actor_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resource_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    room_id: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    orchestration_run_id: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False, default="allowed")
    reason_code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    policy_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class FallbackApprovalRequestModel(Base):
    __tablename__ = "fallback_approval_requests"

    request_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    room_id: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    orchestration_run_id: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    persona_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_provider_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_model_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fallback_provider_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fallback_model_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    trigger_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    rejected_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResumeAdapterPolicyModel(Base):
    __tablename__ = "resume_adapter_policies"

    policy_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        default="",
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft", index=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    rolled_back_from_policy_id: Mapped[str] = mapped_column(Text, nullable=False, default="")


class PromptTemplateVersionModel(Base):
    __tablename__ = "prompt_template_versions"

    template_version_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False, default="openai", index=True)
    template_kind: Mapped[str] = mapped_column(Text, nullable=False, default="system_prompt", index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class PromptTemplateActivationModel(Base):
    __tablename__ = "prompt_template_activations"

    activation_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    scope_level: Mapped[str] = mapped_column(Text, nullable=False, default="tenant", index=True)
    scope_id: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False, default="openai", index=True)
    template_kind: Mapped[str] = mapped_column(Text, nullable=False, default="system_prompt", index=True)
    template_version_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("prompt_template_versions.template_version_id", ondelete="CASCADE"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    rolled_back_from_activation_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ModelGatewayPolicyModel(Base):
    __tablename__ = "model_gateway_policies"

    policy_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False, default="default")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="draft", index=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    rolled_back_from_policy_id: Mapped[str] = mapped_column(Text, nullable=False, default="")


class ToolExecutionModel(Base):
    __tablename__ = "tool_executions"

    execution_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    tool_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="completed")
    input_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    output_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class EmailMessageModel(Base):
    __tablename__ = "email_messages"

    email_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    direction: Mapped[str] = mapped_column(Text, nullable=False, default="outbound")
    sender: Mapped[str] = mapped_column(Text, nullable=False, default="")
    recipients_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    subject: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class StudioOrgInviteModel(Base):
    __tablename__ = "studio_org_invites"

    invite_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    invited_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    accepted_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class StudioOrgSettingModel(Base):
    __tablename__ = "studio_org_settings"

    setting_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    updated_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("org_id", name="uq_studio_org_settings_org"),
    )


class StudioOrgOnboardingModel(Base):
    __tablename__ = "studio_org_onboarding"

    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        primary_key=True,
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    checklist_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    completed_by_user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeDomainModel(Base):
    __tablename__ = "knowledge_domains"

    domain_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parent_domain_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("knowledge_domains.domain_id", ondelete="SET NULL"),
        nullable=True,
    )
    sensitivity_default: Mapped[str] = mapped_column(Text, nullable=False, default="internal")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (UniqueConstraint("tenant_id", "org_id", "name", name="uq_knowledge_domains_name"),)


class KnowledgeNodeModel(Base):
    __tablename__ = "knowledge_nodes"

    node_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    domain_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("knowledge_domains.domain_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    node_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    sensitivity: Mapped[str] = mapped_column(Text, nullable=False, default="internal")
    source_type: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owner_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeEdgeModel(Base):
    __tablename__ = "knowledge_edges"

    edge_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_node_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("knowledge_nodes.node_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_node_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("knowledge_nodes.node_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visibility: Mapped[str] = mapped_column(Text, nullable=False, default="internal")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "org_id", "from_node_id", "to_node_id", "relationship_type", name="uq_knowledge_edges_relation"),
    )


class KnowledgeEntityModel(Base):
    __tablename__ = "knowledge_entities"

    entity_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    kind_schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    contexts_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    facets_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    owners_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    visibility_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    content_refs_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    quality_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    lifecycle_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    kind_payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeRelationshipModel(Base):
    __tablename__ = "knowledge_relationships"

    relationship_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_entity_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("knowledge_entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    to_entity_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("knowledge_entities.entity_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    relationship_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    directionality: Mapped[str] = mapped_column(Text, nullable=False, default="directed")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    facets_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    visibility_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    source_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class StudioWorkflowDefinitionModel(Base):
    __tablename__ = "studio_workflow_definitions"

    workflow_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    spec_version: Mapped[str] = mapped_column(Text, nullable=False, default="v0.3")
    trigger_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    nodes_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    edges_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    logic_rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    policy_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("tenant_id", "org_id", "name", name="uq_studio_workflow_definitions_org_name"),
    )


class WorkflowRunModel(Base):
    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(Text, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_workflow_definitions.workflow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running", index=True)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    review_context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    matched_rules_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class WorkflowReviewQueueModel(Base):
    __tablename__ = "workflow_review_queue"

    review_id: Mapped[str] = mapped_column(Text, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_workflow_definitions.workflow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    node_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", index=True)
    reason_code: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requested_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    context_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkspaceRecordModel(Base):
    __tablename__ = "workspace_records"

    workspace_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False, default="window")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", index=True)
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, default="v1")
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    thread_binding_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    state_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class AppAccessGrantModel(Base):
    __tablename__ = "app_access_grants"

    grant_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    app_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    feature_flags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active", index=True)
    granted_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("org_id", "user_id", "app_id", name="uq_app_access_grants_org_user_app"),
    )


class GeneratedArtifactModel(Base):
    __tablename__ = "generated_artifacts"

    artifact_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_channels.channel_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("workspace_records.workspace_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    orchestration_run_id: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    message_id: Mapped[str] = mapped_column(Text, nullable=False, default="", index=True)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False, default="markdown", index=True)
    producer_type: Mapped[str] = mapped_column(Text, nullable=False, default="persona")
    producer_id: Mapped[str] = mapped_column(Text, nullable=False, default="")
    title: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_by_user_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class DailySummaryModel(Base):
    __tablename__ = "daily_summaries"

    summary_id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    org_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_organizations.org_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("studio_users.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    highlights_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    sections_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    stats_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "org_id",
            "user_id",
            "summary_date",
            name="uq_daily_summaries_tenant_org_user_date",
        ),
    )
