from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('courses', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP INDEX IF EXISTS courses_period_gist_idx;",
            reverse_sql="""
                CREATE INDEX IF NOT EXISTS courses_period_gist_idx
                ON courses USING GIST (tstzrange(start_at, end_at, '[]'))
                WHERE is_active = TRUE;
            """,
        ),
        migrations.AddIndex(
            model_name='course',
            index=models.Index(fields=['is_active'], name='courses_is_acti_25e634_idx'),
        ),
    ]


