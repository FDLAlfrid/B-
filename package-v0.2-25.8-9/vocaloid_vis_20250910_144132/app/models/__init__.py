from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from .. import db

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar_url = db.Column(db.String(255), default='default_avatar.jpg')
    bio = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # 关系
    interests = db.relationship('UserInterest', backref='user', lazy=True, cascade='all, delete-orphan')
    shares = db.relationship('MusicShare', backref='user', lazy=True, cascade='all, delete-orphan')
    favorites = db.relationship('MusicFavorite', backref='user', lazy=True, cascade='all, delete-orphan')

class Music(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bvid = db.Column(db.String(20), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    cover_url = db.Column(db.String(255))
    play_url = db.Column(db.String(255))
    duration = db.Column(db.Integer)  # 时长(秒)
    tags = db.Column(db.String(255))
    view_count = db.Column(db.Integer, default=0)
    pubdate = db.Column(db.Integer)  # B站发布时间戳
    crawl_time = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(db.String(50), default='其他')  # 分类信息：VOCALOID·UTAU、华语、其他
    rid = db.Column(db.Integer, default=0)  # B站分区ID
    
    # 关系
    shares = db.relationship('MusicShare', backref='music', lazy=True)
    favorites = db.relationship('MusicFavorite', backref='music', lazy=True)

class UserInterest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    interest = db.Column(db.String(50), nullable=False)
    interest_level = db.Column(db.Integer, default=1)  # 兴趣程度1-5
    
    __table_args__ = (db.UniqueConstraint('user_id', 'interest', name='unique_user_interest'),)

class MusicShare(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    music_id = db.Column(db.Integer, db.ForeignKey('music.id'), nullable=False)
    share_text = db.Column(db.Text)
    share_time = db.Column(db.DateTime, default=datetime.utcnow)
    platform = db.Column(db.String(20), default='internal')  # internal, weibo, wechat等

class MusicFavorite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    music_id = db.Column(db.Integer, db.ForeignKey('music.id'), nullable=False)
    favorite_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'music_id', name='unique_user_favorite'),)

class UserMusicInteraction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    music_id = db.Column(db.Integer, db.ForeignKey('music.id'), nullable=False)
    interaction_type = db.Column(db.String(20), nullable=False)  # like, play, share, comment
    interaction_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('user_id', 'music_id', 'interaction_type', name='unique_user_music_interaction'),)

class UserMatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    match_score = db.Column(db.Float)
    match_time = db.Column(db.DateTime, default=datetime.utcnow)
    is_mutual = db.Column(db.Boolean, default=False)
    
    __table_args__ = (db.UniqueConstraint('user1_id', 'user2_id', name='unique_user_match'),)