# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone
from django.conf import settings
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('edx_proctoring', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProctoredExamStudentAttemptCustom',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('attempt_id', models.IntegerField(null=True)),
                ('started_at', models.DateTimeField(null=True)),
                ('completed_at', models.DateTimeField(null=True)),
                ('attempt_code', models.CharField(max_length=255, null=True, db_index=True)),
                ('external_id', models.CharField(max_length=255, null=True, db_index=True)),
                ('allowed_time_limit_mins', models.IntegerField(null=True)),
                ('status', models.CharField(max_length=64)),
                ('taking_as_proctored', models.BooleanField(default=False)),
                ('is_sample_attempt', models.BooleanField(default=False)),
                ('student_name', models.CharField(max_length=255)),
                ('review_policy_id', models.IntegerField(null=True)),
                ('last_poll_timestamp', models.DateTimeField(null=True)),
                ('last_poll_ipaddr', models.CharField(max_length=32, null=True)),
                ('service', models.CharField(max_length=255, null=True)),
                ('proctored_exam', models.ForeignKey(to='edx_proctoring.ProctoredExam')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'proctoring_proctoredexamstudentattemptcustom',
                'verbose_name': 'proctored exam attempt custom',
            },
        ),
    ]
