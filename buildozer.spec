[app]

title = B站BV号查询
package.name = bilibili_query
package.domain = org.test

source.include_exts = py,png,jpg,kv,atlas,json
source.dir = .

version = 1.0.0

requirements = python3,kivy,requests,pyjnius,openssl,cryptography

orientation = portrait

fullscreen = 0

android.permissions = INTERNET

android.api = 33
android.minapi = 19
android.ndk = 25b

android.archs = arm64-v8a,armeabi-v7a

[buildozer]

log_level = 2

warn_on_root = 1
