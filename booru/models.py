import os
import uuid

import reversion
from django.contrib.contenttypes.fields import (GenericForeignKey,
                                                GenericRelation)
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Sum
from django.urls import reverse
from taggit.managers import TaggableManager
from taggit.models import GenericTaggedItemBase, TagBase

from account.models import Account

from . import utils
from .managers import PostManager


def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = "%s.%s" % (uuid.uuid4(), ext)
    return filename

def get_file_path_preview(instance, filename):
    name = get_file_path(instance, filename)
    return os.path.join('data/preview/', name)

def get_file_path_sample(instance, filename):
    name = get_file_path(instance, filename)
    return os.path.join('data/sample/', name)

def get_file_path_image(instance, filename):
    name = get_file_path(instance, filename)
    return os.path.join('data/image/', name)

class Comment(models.Model):
    author = models.ForeignKey(Account, on_delete=models.CASCADE)
    content = models.CharField(max_length=1000, blank=True)
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)
    update_timestamp = models.DateTimeField(auto_now=True, auto_now_add=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def get_vote_count(self):
        return self.commentvote_set.count()
    
    def get_score(self):
        upvotes = self.commentvote_set.filter(point=1).count()
        downvotes = self.commentvote_set.filter(point=-1).count()
        return upvotes - downvotes

class Implication(models.Model):
    from_tag = models.ForeignKey('booru.PostTag', blank=True, null=True, default=None, on_delete=models.CASCADE, related_name="from_implications")    
    to_tag = models.ForeignKey('booru.PostTag', blank=True, null=True, default=None, on_delete=models.CASCADE, related_name="to_implications")    
    author = models.ForeignKey(Account, null=True, on_delete=models.SET_NULL, related_name="authored_implications")
    approver = models.ForeignKey(Account, blank=True, null=True, default=None, on_delete=models.SET_NULL, related_name="approved_implications")
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)
    
    PENDING = 0
    APPROVED = 1
    UNAPPROVED = 2
    STATUS_CHOICES = (
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (UNAPPROVED, 'Unapproved')
    )
    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    def __str__(self):
        return "{} -> {}".format(self.from_tag, self.to_tag)

class Category(models.Model):
    '''Basic model for the content app. It should be inherited from the other models.'''
    label = models.CharField(max_length=100, blank=True)
    title_singular = models.CharField(max_length=100, blank=True)
    title_plural = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=6, blank=True)

    def __str__(self):
        return self.title_singular

    class Meta:
        verbose_name_plural = 'Categories'

@reversion.register()
class PostTag(TagBase):
    category = models.ForeignKey(Category, default=1, on_delete=models.SET_DEFAULT)
    description = models.CharField(max_length=100, blank=True)
    associated_link = models.CharField(max_length=100, blank=True)
    associated_user = models.ForeignKey(Account, null=True, blank=True,
                                                 on_delete=models.SET_NULL, related_name="associated_tags")
    author = models.ForeignKey(Account, null=True, on_delete=models.SET_NULL, related_name="authored_tags")
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)
    aliases = TaggableManager()

    class Meta:
        verbose_name = ("Tag")
        verbose_name_plural = ("Tags")

    def get_absolute_url(self):
        return reverse('booru:tag_detail', kwargs={'tag_id': self.id})

    def get_count(self):
        return TaggedPost.objects.filter(tag=self).count()

#@reversion.register()
class TaggedPost(GenericTaggedItemBase):
    tag = models.ForeignKey(PostTag, related_name="%(app_label)s_%(class)s_items", on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        super(TaggedPost, self).save(*args, **kwargs)

        tag_name = self.tag
        utils.verify_and_perform_implications(tag_name)

@reversion.register()
class Gallery(models.Model):
    name = models.CharField(max_length=100, blank=True)
    description = models.CharField(max_length=1000, blank=True)
    posts = models.ManyToManyField('booru.Post')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return "{}".format(self.name)
    
    def get_count(self):
        return self.posts.count()

    def get_absolute_url(self):
        return reverse('booru:gallery_detail', kwargs={'gallery_id': self.id})

@reversion.register()
class Post(models.Model):
    parent = models.IntegerField(null=True, blank=True)
    preview = models.ImageField(upload_to=get_file_path_preview, blank=True)
    sample = models.ImageField(upload_to=get_file_path_sample, blank=True)
    image = models.ImageField(upload_to=get_file_path_image, blank=True)
    uploader = models.ForeignKey(Account, null=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(auto_now=False, auto_now_add=True)
    update_timestamp = models.DateTimeField(auto_now=True, auto_now_add=False)
    source = models.TextField(blank=True)
    score = models.IntegerField(default=0)
    identifier = models.UUIDField(default=uuid.uuid4, editable=False)
    locked = models.BooleanField(default=False)
    tags = TaggableManager(through=TaggedPost, related_name="posts")
    tags_mirror = models.CharField(max_length=1000, blank=True)
    description = models.TextField(max_length=1000, blank=True)
    comments = GenericRelation(Comment)

    objects = PostManager()

    NONE = 0
    SAFE = 1
    QUESTIONABLE = 2
    EXPLICIT = 3
    RATING_CHOICES = (
        (NONE, 'None'),
        (SAFE, 'Safe'),
        (QUESTIONABLE, 'Questionable'),
        (EXPLICIT, 'Explicit')
    )
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        default=NONE,
    )

    PENDING = 0
    APPROVED = 1
    HIDDEN = 2
    DELETED = 3
    STATUS_CHOICES = (
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (HIDDEN, 'Hidden'),
        (DELETED, 'Deleted')
    )
    status = models.IntegerField(
        choices=STATUS_CHOICES,
        default=PENDING,
    )

    def __str__(self):
        return "#{}".format(self.id)

    def save(self, *args, **kwargs):
        pil_image = utils.get_pil_image_if_valid(self.image)

        if pil_image:
            sample = utils.get_sample(pil_image)
            preview = utils.get_preview(pil_image)
            
            if sample:
                self.sample.save(".jpg", sample, save=False)

            self.preview.save(".jpg", preview, save=False)

        if self.id:
            self.mirror_tags()
        super(Post, self).save(*args, **kwargs)

    def get_sample_url(self):
        if self.sample:
            return self.sample.url
        else:
            return self.image.url

    def get_absolute_url(self):
        return reverse('booru:post_detail', kwargs={'post_id': self.id})

    def get_ordered_tags(self):
        ordered_tags = {}
        tags = self.tags.all().order_by('category', 'name')
        
        for tag in tags:
            try:
                ordered_tags[tag.category]
            except:
                ordered_tags[tag.category] = []
            ordered_tags[tag.category].append(tag)
        
        return ordered_tags

    def get_score_count(self):
        votes = ScoreVote.objects.filter(post=self)
        
        if votes.exists():
            votes = votes.aggregate(Sum('point'))['point__sum']
        else:
            votes = 0
        
        return votes

    def get_favorites_count(self):
        return self.favorites.count()

    def mirror_tags(self):
        self.tags_mirror = " ".join(self.tags.names())

    class Meta:
        permissions = (
            ("change_status", "Can change the status of posts"),
            ("mass_rename", "Can mass rename posts"),
        )


class Favorite(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="account_favorites")
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="favorites")

    class Meta:
        unique_together = ('account', 'post',)

class ScoreVote(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    point = models.IntegerField(default=1)

    class Meta:
        unique_together = ('account', 'post',)

class CommentVote(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE)
    point = models.IntegerField(default=1)

    class Meta:
        unique_together = ('account', 'comment',)
