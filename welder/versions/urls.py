from django.conf.urls import url
from welder.versions import views

urlpatterns = [
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/create$', views.create_project, name='create-project'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/createbranch$', views.create_branch, name='create-branch'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/fork$', views.fork_project, name='fork-project'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/rename$', views.rename_project, name='rename-project'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/delete$', views.delete_project, name='delete-project'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/deletefiles$', views.delete_files, name='delete-files'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/deletebranch$', views.delete_branch, name='delete-branch'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/revert$', views.revert_commit, name='revert-commit'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/readfile$', views.read_file, name='read-file'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/readhistory$', views.read_history, name='read-history'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/upload$', views.receive_files, name='receive-files'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/listbom$', views.list_bom, name='list-bom'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/listbranches$', views.list_branches, name='list_branches'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/listaheadbehind$', views.list_branches_ahead_behind, name='list_branches_ahead_behind'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)/archive/download$', views.download_archive, name='download-archive'),
    url(r'^(?P<user>[-.\w]+)/(?P<project_name>[-.+\w\s]+)$', views.read_tree, name='read-tree'),
]
