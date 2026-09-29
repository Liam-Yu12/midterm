import getpass
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from billing.models import BillingAccount


class Command(BaseCommand):
    help = (
        'Create or update a demo user with an active [Personal] billing account. '
        'Safe to re-run: the account credit is reset to --credit.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument(
            '--password',
            help='Omit to be prompted, which keeps the password out of shell history and transcripts.',
        )
        parser.add_argument('--credit', default='2.00', help='Account credit in USD (default: 2.00).')

    def handle(self, *args, username, password, credit, **options):
        try:
            credit = Decimal(credit)
        except InvalidOperation:
            raise CommandError(f'Invalid --credit value: {credit!r}')
        if credit < 0:
            raise CommandError('--credit must not be negative.')

        if not password:
            password = getpass.getpass(f'Password for {username}: ')
        if not password:
            raise CommandError('A password is required.')

        with transaction.atomic():
            user, user_created = get_user_model().objects.get_or_create(username=username)
            user.set_password(password)
            user.save()

            account = user.billing_accounts.filter(kind=BillingAccount.Kind.PERSONAL).first()
            account_created = account is None
            if account_created:
                account = BillingAccount.objects.create(
                    name=(user.get_full_name() or user.get_username()).upper(),
                    kind=BillingAccount.Kind.PERSONAL,
                )
                account.members.add(user)
            account.status = BillingAccount.Status.ACTIVE
            account.credit = credit
            account.save()

        self.stdout.write(self.style.SUCCESS(
            f"{'Created' if user_created else 'Updated'} user '{username}'; "
            f"{'created' if account_created else 'updated'} {account} with ${credit:.2f} credit."
        ))
