# -*- coding: utf-8 -*-
import re
import os
from datetime import date, datetime
from django.conf import settings
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.db.models.signals import post_save
from django.utils.safestring import mark_safe
from model_utils import Choices
from apps.front import fields


class Lecturer(models.Model):
    """A lecturer at HSR.

    If there is a photo of that lecturer, it should go into the media folder
    and the filename should be <abbreviation>.jpg.

    """
    id = models.IntegerField(u'HSR ID', primary_key=True)
    title = models.CharField(u'Titel', max_length=32, null=True, blank=True)
    last_name = models.CharField(u'Name', max_length=255)
    first_name = models.CharField(u'Vorname', max_length=255)
    abbreviation = models.CharField(u'Kürzel', max_length=10, unique=True)
    department = models.CharField(u'Abteilung', max_length=100, null=True, blank=True)
    function = models.CharField(u'Funktion', max_length=255, null=True, blank=True)
    main_area = models.CharField(u'Fachschwerpunkt', max_length=255, null=True, blank=True)
    subjects = models.CharField(max_length=50, null=True, blank=True)  # todo add to frontend
    description = models.TextField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    office = models.CharField(max_length=20, null=True, blank=True)

    def name(self):
        parts = filter(None, [self.title, self.last_name, self.first_name])
        return ' '.join(parts)

    def photo(self):
        """Try to see if a photo with the name <self.id>.jpg exists. If it
        does, return the corresponding URL. If it doesn't, return None."""
        path = os.path.join('lecturers', '%s.jpg' % self.id)
        fullpath = os.path.join(settings.MEDIA_ROOT, path)
        return path if os.path.exists(fullpath) else None

    def oldphotos(self):
        """Try to see whether there are more pictures in the folder
        ``lecturers/old/<self.id>/``..."""
        path = os.path.join('lecturers', 'old', str(self.id))
        fullpath = os.path.join(settings.MEDIA_ROOT, path)
        oldphotos = []
        if os.path.exists(fullpath):
            for filename in os.listdir(fullpath):
                if re.match(r'^[0-9]+\.jpg$', filename):
                    filepath = os.path.join(path, filename)
                    oldphotos.append(filepath)
        return oldphotos

    # TODO rename to _rating_avg
    def _avg_rating(self, category):
        """Calculate the average rating for the given category."""
        qs = self.LecturerRating.filter(category=category)
        if qs.exists():
            ratings = qs.values_list('rating', flat=True)
            return int(round(float(sum(ratings)) / len(ratings)))
        return 0

    def _rating_count(self, category):
        return self.LecturerRating.filter(category=category).count()

    def avg_rating_d(self):
        return self._avg_rating(u'd')

    def avg_rating_m(self):
        return self._avg_rating(u'm')

    def avg_rating_f(self):
        return self._avg_rating(u'f')

    def rating_count_d(self):
        return self._rating_count(u'd')

    def rating_count_m(self):
        return self._rating_count(u'm')

    def rating_count_f(self):
        return self._rating_count(u'f')

    def __unicode__(self):
        return '%s %s' % (self.last_name, self.first_name)

    class Meta:
        ordering = ['last_name']


class LecturerRating(models.Model):
    """A lecturer rating. Max 1 per user, category and lecturer."""
    CATEGORY_CHOICES = (
        (u'd', 'Didaktisch'),
        (u'm', 'Menschlich'),
        (u'f', 'Fachlich'))

    user = models.ForeignKey(User, related_name=u'LecturerRating')
    lecturer = models.ForeignKey(Lecturer, related_name=u'LecturerRating')
    category = models.CharField(max_length=1, choices=CATEGORY_CHOICES, db_index=True)
    rating = models.PositiveSmallIntegerField(validators=[MaxValueValidator(10), MinValueValidator(1)], db_index=True)

    def __unicode__(self):
        return '%s %s%u' % (self.lecturer, self.category, self.rating)

    class Meta:
        unique_together = ('user', 'lecturer', 'category')


class Quote(models.Model):
    """Lecturer quotes."""
    author = models.ForeignKey(User, related_name='Quote', null=True, on_delete=models.SET_NULL)
    lecturer = models.ForeignKey(Lecturer, verbose_name=u'Dozent', related_name='Quote')
    date = models.DateTimeField(auto_now_add=True)
    quote = models.TextField(u'Zitat')
    comment = models.TextField(u'Bemerkung', default=u'', blank=True)

    def date_available(self):
        return self.date != datetime(1970, 1, 1)

    def vote_sum(self):
        """Add up and return all votes for this quote."""
        up = self.QuoteVote.filter(vote=True).count()
        down = self.QuoteVote.filter(vote=False).count()
        return up - down

    def __unicode__(self):
        return u'[%s] %s...' % (self.lecturer, self.quote[:30])

    class Meta:
        ordering = ['-date']


class QuoteVote(models.Model):
    """Lecturer quotes."""
    user = models.ForeignKey(User, related_name='QuoteVote')
    quote = models.ForeignKey(Quote, related_name='QuoteVote')
    vote = models.BooleanField(help_text='True = upvote, False = downvote')

    def __unicode__(self):
        return 'User %s votes %s quote %s' % (self.user.username, 'up' if self.vote else 'down', self.quote.pk)

    class Meta:
        unique_together = ('user', 'quote')


class DocumentCategory(models.Model):
    """Categories (usually subjects) for the documents.

    A document can have several categories.

    """
    name = fields.CaseInsensitiveSlugField(u'Kürzel', max_length=32, unique=True,
            help_text=u'z.B. "CompT1" oder "Prog3"')
    description = models.CharField(u'Voller Name', max_length=255,
            help_text=u'z.B. "Computertechnik 1" oder "Programmieren 3"')
    is_module = models.BooleanField(default=True, verbose_name=u'Unterrichtsmodul',
            help_text='Ob diese Kategorie ein Unterrichtsmodul ist oder nicht.')

    @property
    def summary_count(self):
        return self.Document.filter(dtype=Document.DTypes.SUMMARY).count()

    @property
    def exam_count(self):
        return self.Document.filter(dtype=Document.DTypes.EXAM).count()

    @property
    def other_count(self):
        excludes = [Document.DTypes.EXAM, Document.DTypes.SUMMARY]
        return self.Document.exclude(dtype__in=excludes).count()

    def __unicode__(self):
        return self.name

    class Meta:
        verbose_name = u'Modul'
        ordering = ['name']


class Document(models.Model):
    """A document that can be uploaded by students.

    A document can have a description, categories, ratings, etc...

    """
    class DTypes(object):
        """Enum-style document type class."""
        SUMMARY=1
        EXAM=2
        SOFTWARE=3
        LEARNING_AID=4

    LICENSES=Choices(
        (1, 'pd', 'Public Domain'),
        (2, 'cc3_by', 'CC BY 3.0'),
        (3, 'cc3_by_sa', 'CC BY-SA 3.0'),
        (4, 'cc3_by_nc', 'CC BY-NC 3.0'),
        (5, 'cc3_by_nc_sa', 'CC BY-NC-SA 3.0'),
    )

    def document_file_name(instance, filename):
        """Where to put a newly uploaded document. Also, store original filename."""
        ext = os.path.splitext(filename)[1]
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        instance.original_filename = filename
        return '/'.join(['documents', slugify(instance.category.name), '%s%s' % (timestamp, ext)])

    name = models.CharField(u'Titel', max_length=100)
    description = models.CharField(u'Beschreibung', blank=True, max_length=500,
        help_text=u'(Max. 500 Zeichen)')
    url = models.URLField(u'URL', null=True, blank=True,
        help_text=u'z.B. Link zu Github Repository')
    category = models.ForeignKey(DocumentCategory, verbose_name=u'Modul', related_name=u'Document', null=True, on_delete=models.PROTECT)
    dtype = models.PositiveSmallIntegerField(u'Typ', choices=(
        (DTypes.SUMMARY, u'Zusammenfassung'),
        (DTypes.EXAM, u'Prüfung'),
        (DTypes.SOFTWARE, u'Software'),
        (DTypes.LEARNING_AID, u'Lernhilfe'),
        ))
    document = models.FileField(u'Datei', upload_to=document_file_name, help_text=u'(Max. 10MB)')
    original_filename = models.CharField(u'Originaler Dateiname', max_length=255, blank=True)
    uploader = models.ForeignKey(User, related_name=u'Document', null=True, on_delete=models.SET_NULL)
    upload_date = models.DateTimeField(u'Uploaddatum', auto_now_add=True)
    change_date = models.DateTimeField(u'Letztes Änderungsdatum')
    license = models.PositiveSmallIntegerField(u'Lizenz', choices=LICENSES, null=True, blank=True,
        help_text=mark_safe('Lizenz, siehe <a href="http://creativecommons.org/choose/?lang=de">' + 
            'http://creativecommons.org/choose/?lang=de</a> um eine passende Lizenz auszuwählen.' +
            '<br>Empfohlen: CC BY-SA-NC 3.0'))

    def rating_exact(self):
        """Return exact rating average."""
        ratings = self.DocumentRating.values_list('rating', flat=True)
        total = sum(ratings)
        if len(ratings) > 0:
            return float(total) / len(ratings)
        else:
            return 0

    def rating(self):
        """Return rounded rating average."""
        return int(round(self.rating_exact()))
        
    def filename(self):
        """Return filename of uploaded file without directories."""
        return os.path.basename(self.document.name)

    def fileext(self):
        """Return file extension by splitting at last occuring period."""
        return os.path.splitext(self.document.name)[1]

    def exists(self):
        """Return whether or not the file exists on the harddrive."""
        return os.path.exists(self.document.path)

    def downloadcount(self):
        """Return the download count."""
        return self.DocumentDownload.count()

    def license_details(self):
        """Return the URL to the license and the appropriate license icon."""
        CC_LICENSES={2: 'by', 3: 'by-sa', 4: 'by-nc', 5: 'by-nc-sa'}
        if self.license in CC_LICENSES.keys():
            url_template = 'http://creativecommons.org/licenses/{0}/3.0/deed.de'
            icon_template = 'http://i.creativecommons.org/l/{0}/3.0/80x15.png'
            url = url_template.format(CC_LICENSES.get(self.license))
            icon = icon_template.format(CC_LICENSES.get(self.license))
        elif self.license == 1:
            url = 'http://creativecommons.org/publicdomain/zero/1.0/deed.de'
            icon = 'http://i.creativecommons.org/p/zero/1.0/80x15.png'
        else:
            url = icon = None
        return {'url': url, 'icon': icon, 'name': self.get_license_display()}

    def save(self, *args, **kwargs):
        """Override save method to automatically set change_date at creation."""
        if not self.change_date:
            self.change_date = datetime.now()
        return super(Document, self).save(*args, **kwargs)

    def __unicode__(self):
        return self.name

    class Meta:
        ordering = ('-change_date',)
        get_latest_by = 'change_date'


class DocumentDownload(models.Model):
    """Tracks a download of a document."""
    # TODO django 1.5: index_together on document/timestamp/ip
    document = models.ForeignKey(Document, related_name=u'DocumentDownload', db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, editable=False)
    ip = models.GenericIPAddressField(unpack_ipv4=True, editable=False, db_index=True)


class DocumentRating(models.Model):
    """Rating for a document.

    Valid values are integers between 1 and 5.

    """
    user = models.ForeignKey(User, related_name=u'DocumentRating')
    document = models.ForeignKey(Document, related_name='DocumentRating')
    rating = models.PositiveSmallIntegerField(validators=[MaxValueValidator(10), MinValueValidator(1)])

    # Custom model validation
    def clean(self):
        if self.user == self.document.uploader:
            raise ValidationError(u'A user cannot rate his own uploads.')

    def __unicode__(self):
        return 'User %s Document %s Rating %u' % (self.user.username, self.document.name, self.rating)

    class Meta:
        unique_together = ('user', 'document')


class ModuleReview(models.Model):
    """Review of a module."""
    SEMESTER_CHOICES = (
        (u'h', u'Herbstsemester'),
        (u'f', u'Frühlingssemester'))
    TOPIC_RATINGS = (
        (1, u'Sehr Langweilig'),
        (2, u'Langweilig'),
        (3, u'Normal'),
        (4, u'Interessant'),
        (5, u'Sehr Interessant'))
    UNDERSTANDABILITY_RATINGS = (
        (1, u'Katastrophal'),
        (2, u'Unverständlich'),
        (3, u'Normal'),
        (4, u'Verständlich'),
        (5, u'Genial'))
    EFFORT_RATINGS = (
        (1, u'Sehr Hoch'),
        (2, u'Hoch'),
        (3, u'Normal'),
        (4, u'Gering'),
        (5, u'Sehr Gering'))
    DIFFICULTY_RATINGS = (
        (1, u'Sehr Schwierig'),
        (2, u'Schwierig'),
        (3, u'Normal'),
        (4, u'Einfach'),
        (5, u'Sehr Einfach'))

    Module = models.ForeignKey(DocumentCategory, related_name=u'ModuleReview')
    Lecturer = models.ForeignKey(Lecturer, related_name=u'ModuleReview')
    semester = models.CharField(u'Semester', max_length=1, choices=SEMESTER_CHOICES)
    year = models.PositiveIntegerField(u'Jahr')
    topic = models.SmallIntegerField(u'Thematik', choices=TOPIC_RATINGS,
            help_text=u'Wie interessant war die Thematik?')
    understandability = models.SmallIntegerField(u'Verständlichkeit', choices=UNDERSTANDABILITY_RATINGS,
            help_text=u'Wie verständlich war der Unterricht?')
    effort = models.SmallIntegerField(u'Aufwand', choices=EFFORT_RATINGS,
            help_text=u'Wie aufwändig war das Modul?')
    difficulty_module = models.SmallIntegerField(u'Schwierigkeit Modul', choices=DIFFICULTY_RATINGS,
            help_text=u'Wie schwierig war das Modul inhaltlich?')
    difficulty_exam = models.SmallIntegerField(u'Schwierigkeit Prüfung', choices=DIFFICULTY_RATINGS,
            help_text=u'Wie schwierig war die Prüfung?')
    comment = models.TextField(u'Allgemeines Feedback', blank=True, null=True,
            help_text=u'Allgemeines Feedback zum Modul.')


class Event(models.Model):
    """An event.

    If end_date is null, then assume end_date = start_date.

    """

    def picture_file_name(instance, filename):
        """Where to put a newly uploaded picture."""
        return '/'.join(['event_pictures', str(instance.start_date.year), filename])

    author = models.ForeignKey(User, related_name='Event', null=True, on_delete=models.SET_NULL)
    summary = models.CharField(u'Titel', max_length=64)
    description = models.TextField(u'Beschreibung')
    start_date = models.DateField(u'Startdatum',
            help_text=u'Format: dd.mm.YYYY')
    start_time = models.TimeField(u'Startzeit', null=True, blank=True,
            help_text=u'Format: hh:mm')
    end_date = models.DateField(u'Enddatum', null=True, blank=True,
            help_text=u'Format: dd.mm.YYYY')
    end_time = models.TimeField(u'Endzeit', null=True, blank=True,
            help_text=u'Format: hh:mm')
    location = models.CharField(u'Ort', max_length=80, null=True, blank=True,
            help_text=u'Veranstaltungsort, zB "Gebäude 3" oder "Bären Rapperswil"')
    url = models.URLField(u'URL', null=True, blank=True,
            help_text=u'URL zu Veranstaltungs-Website')
    picture = models.ImageField(u'Bild/Flyer', upload_to=picture_file_name, null=True, blank=True,
            help_text=u'Bild oder Flyer')

    def is_over(self):
        """Return whether the start_date has already passed or not.
        On the start_date day itself, is_over() will return False."""
        delta = self.start_date - date.today()
        return delta.days < 0

    def all_day(self):
        """Return whether the event runs all day long.
        This is the case if start_time and end_time are not set."""
        return self.start_time == self.end_time == None

    def days_until(self):
        """Return how many days are left until the day of the event."""
        delta = self.start_date - date.today()
        return delta.days if delta.days > 0 else None

    def __unicode__(self):
        return '%s %s' % (self.start_date, self.summary)


class UserProfile(models.Model):
    """A user profile."""
    user = models.OneToOneField(User)
    twitter = models.CharField(u'Twitter Benutzername', max_length=24, blank=True)
    flattr = models.CharField(u'Flattr Benutzername', max_length=128, blank=True,
            help_text=mark_safe(u'Falls angegeben, wird bei deinen \
            Zusammenfassungen jeweils ein \
            <a href="https://flattr.com/">Flattr</a> Button angezeigt.'))

    def __unicode__(self):
        return u'Profile for %s' % self.user.username


User.profile = property(lambda u: UserProfile.objects.get_or_create(user=u)[0])


def name(self):
    """Return either full user first and last name or the username, if no
    further data is found."""
    if self.first_name or self.last_name:
        return ' '.join(filter(None, [self.first_name, self.last_name]))
    return self.username
User.add_to_class('name', name)


def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
post_save.connect(create_user_profile, sender=User)
