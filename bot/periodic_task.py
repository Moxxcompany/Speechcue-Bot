from django_celery_beat.models import PeriodicTask, IntervalSchedule

def create_periodic_task():
    schedule_check_call, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.MINUTES,
    )

    PeriodicTask.objects.update_or_create(
        interval=schedule_check_call,
        name='Check Call Status Task',
        task='bot.tasks.check_call_status',
    )

    schedule_charge_user, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.MINUTES,
    )

    PeriodicTask.objects.update_or_create(
        interval=schedule_charge_user,
        name='Charge Users for Additional Minutes Task',
        task='bot.tasks.charge_user_for_additional_minutes',
    )
    schedule_notify_user, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.MINUTES,
    )

    PeriodicTask.objects.update_or_create(
        interval=schedule_notify_user,
        name='Notify Users for Additional Minutes Payment',
        task='bot.tasks.notify_users',
    )
    schedule_call_status_free_plan, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.MINUTES,
    )

    PeriodicTask.objects.update_or_create(
        interval=schedule_call_status_free_plan,
        name='Calculate additional minutes for single ivr calls',
        task='bot.tasks.call_status_free_plan',
    )

    print("All periodic tasks created successfully.")


