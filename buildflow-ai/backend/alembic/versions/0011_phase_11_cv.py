"""Phase 11 - Computer Vision tables.

Creates:
- detection_results
- site_photos
- ppe_registrations
"""
from alembic import op
import sqlalchemy as sa
import uuid as uuid_module


# revision identifiers, used by Alembic.
revision = "0011_phase_11_cv"
down_revision = "0010_phase_10_ml"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "detection_results",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("photo_id", sa.Uuid, sa.ForeignKey("site_photos.id"), nullable=True, index=True),
        sa.Column("detections", sa.Text, nullable=False, default="[]"),
        sa.Column("confidence_threshold", sa.Float, nullable=False, default=0.5),
        sa.Column("is_approved", sa.Boolean, nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "site_photos",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id"), nullable=True, index=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("caption", sa.Text, nullable=True),
        sa.Column("uploaded_by", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("analysis_status", sa.String(20), nullable=False, default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "ppe_registrations",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("organization_id", sa.Uuid, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("role_name", sa.String(50), nullable=False),
        sa.Column("required_ppetypes", sa.Text, nullable=False, default="[]"),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_table("ppe_registrations")
    op.drop_table("site_photos")
    op.drop_table("detection_results")