from django.views.decorators.http import require_http_methods
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.http import HttpResponseBadRequest
from django.http import StreamingHttpResponse
from django.conf import settings

from welder.permissions import decorators as permissions
from welder.notifications import decorators as notification
from welder.versions import decorators as errors
from welder.uploads import decorators as uploads
from welder.versions.utilities import fetch_repository
from welder.versions.utilities import split_commit_message
from welder.versions import porcelain as porcelain

from wsgiref.util import FileWrapper
from pygit2 import GIT_SORT_TIME
from io import BytesIO
from time import time
from enum import Enum
import mimetypes
import itertools
import tokenlib
import logging
import tarfile
import base64
import pygit2
import shutil
import json
import os

logger = logging.getLogger(__name__)

@require_http_methods(["POST", "OPTIONS"])
@permissions.requires_permission_to("create")
@errors.catch
def create_project(request, user, project_name, permissions_token):
    """ Creates a bare repository (project) based on the user name
        and project name in the URL.

        It generates a unique path based on the user name and
        project, creates a default documentation and commits it.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        HttpResponse: A message indicating the success or failure of the create
    """

    print(request)
    logger.info(request)
    directory = porcelain.generate_directory(user)
    path = os.path.join(settings.REPO_DIRECTORY, directory, project_name)

    if not os.path.exists(os.path.join(settings.REPO_DIRECTORY, directory)):
        os.makedirs(os.path.join(settings.REPO_DIRECTORY, directory))

    if os.path.exists(path):
        response = HttpResponseBadRequest("You already have a project with this name")
        return response

    repo = pygit2.init_repository(path, True)
    tree = repo.TreeBuilder()
    message = "Project created"
    author = pygit2.Signature('Wevolver', 'Wevolver')
    comitter = pygit2.Signature('Wevolver', 'Wevolver')

    with open('welder/versions/helpers/attributes','r') as attributes:
        attributes = attributes.read()

    attributes = repo.create_blob(attributes)
    tree.insert('.gitattributes', attributes, pygit2.GIT_FILEMODE_BLOB)
    sha = repo.create_commit('HEAD', author, comitter, message, tree.write(), [])
    response = HttpResponse("Created at ./repos/{}/{}".format(user, project_name))
    return response

@require_http_methods(["POST", "OPTIONS"])
@permissions.requires_permission_to("create")
@errors.catch
def create_branch(request, user, project_name, permissions_token):
    post = json.loads(request.body)
    repo = fetch_repository(user, project_name)
    branch = post['branch_name']
    origin_branch = post['origin_branch']
    commit = repo[repo.branches.get(origin_branch).target]
    reference = repo.branches.create(branch, commit)
    response = HttpResponse("Created branch {} on ./repos/{}/{}".format(branch, user, project_name))
    return response

@require_http_methods(["POST", "OPTIONS"])
@permissions.requires_permission_to("create")
@errors.catch
def fork_project(request, user, project_name, permissions_token):
    """ Creates a bare repository (project) based on the user name
        and project name in the URL.

        It generates a unique path based on the user name and
        project, creates a default documentation and commits it.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        HttpResponse: A message indicating the success or failure of the create
    """
    post = request.POST
    directory = porcelain.generate_directory(user)
    source_path = os.path.join(settings.REPO_DIRECTORY, directory, project_name)
    current_user = post['cloning_user'].lstrip('/').rstrip('/')
    directory = porcelain.generate_directory(current_user)
    destination_path = os.path.join(settings.REPO_DIRECTORY, directory, project_name)
    if not os.path.exists(os.path.join(settings.REPO_DIRECTORY, directory)):
        os.makedirs(os.path.join(settings.REPO_DIRECTORY, directory))
    shutil.copytree(source_path, destination_path)
    response = HttpResponse("Cloned at ./repos/{}/{}".format(user, project_name))
    return response

@require_http_methods(["POST", "OPTIONS"])
@permissions.requires_permission_to("write")
@errors.catch
def rename_project(request, user, project_name, permissions_token=None):
    """ Renames a project


    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        HttpResponse: A message indicating the success or failure of the rename
    """
    post = request.POST
    directory = porcelain.generate_directory(user)
    new_name = post['new_name'].lstrip('/').rstrip('/')
    source_path = os.path.join(settings.REPO_DIRECTORY, directory, project_name)
    destination_path = os.path.join(settings.REPO_DIRECTORY, directory, new_name)
    os.rename(source_path, destination_path)
    response = HttpResponse("Renamed at ./repos/{}/{}".format(user, new_name))
    return response

@require_http_methods(["POST", "OPTIONS"])
@permissions.requires_permission_to('write')
@errors.catch
def delete_project(request, user, project_name, permissions_token):
    """ Finds the repository specified in the URL and deletes from the file system.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        HttpResponse: A message indicating the success or failure of the delete
    """

    directory = porcelain.generate_directory(user)
    path = os.path.join(settings.REPO_DIRECTORY, directory, project_name)
    shutil.rmtree(path)
    response = HttpResponse("Deleted at ./repos/{}/{}".format(user, project_name))
    response['Permissions'] = permissions_token
    return response

@require_http_methods(["POST", "OPTIONS"])
@permissions.requires_permission_to("create")
@errors.catch
def delete_branch(request, user, project_name, permissions_token):
    post =  json.loads(request.body)
    repo = fetch_repository(user, project_name)
    branch = post.get('branch_name')
    if branch:
        repo.branches.delete(branch)
        response = HttpResponse("Deleted branch {} on ./repos/{}/{}".format(branch, user, project_name))
    else:
        response = HttpResponseBadRequest("Missing branch name")
    return response

@require_http_methods(["GET", "OPTIONS"])
@permissions.requires_permission_to('read')
@errors.catch
def read_file(request, user, project_name, permissions_token):
    """ Finds a file in the path of the repository specified by the URL
        and returns the blob.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        StreamingHttpResponse: The file's raw data.
    """
    path = request.GET.get('path').lstrip('/').rstrip('/')
    oid = request.GET.get('oid')
    branch = request.GET.get('branch') if request.GET.get('branch') else 'master'
    download = request.GET.get('download')
    repo = fetch_repository(user, project_name)
    parsed_file = None
    data = None
    type_blob = 3
    if oid:
        git_blob = repo.read(oid)
        if git_blob[0] is type_blob:
            data = git_blob[1]
    else:
        root_tree = repo.revparse_single(branch).tree
        git_tree, git_blob, folder_path = porcelain.walk_tree(repo, root_tree, path)
        if type(git_blob) == pygit2.Blob:
            data = git_blob.data
    # parsed_file = str(base64.b64encode(data), 'utf-8')
    chunk_size = 8192
    filelike = FileWrapper(BytesIO(data), chunk_size)
    response = StreamingHttpResponse(filelike, content_type=mimetypes.guess_type(path)[0])
    response['Content-Length'] = len(data)
    response['Permissions'] = permissions_token
    if download:
        response['Content-Disposition'] = "attachment; filename=%s" % path
    return response

@require_http_methods(["POST", "OPTIONS"])
@uploads.add_handlers
@permissions.requires_permission_to("write")
# #@notification.notify("committed to")
#@notification.activity("committed")
@errors.catch
def receive_files(request, user, project_name, permissions_token=None):
    """ Receives and commits an array of files to a specific path in the repository.

        content_type_extra contains the full path of the file with respect to the root of the tree.
        This is inserted in the custom upload handler.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        JsonResponse: An object
    """

    email = request.POST.get('email', 'git@wevolver.com')
    message = request.POST.get('commit_message', 'received new files')
    name = request.POST.get('user_name', user)
    path = request.POST.get('path', None)
    branch = request.GET.get('branch') if request.GET.get('branch') else None
    repo = fetch_repository(user, project_name)
    if request.FILES and path != None and branch:
        blobs = []
        for key, file in request.FILES.items():
            blob = repo.create_blob(file.read())
            blobs.append((blob, path + file.name))
        new_commit_tree = porcelain.add_blobs_to_tree(repo, branch, blobs)
        porcelain.commit_tree(repo, branch, new_commit_tree, name, email, message)
        response = JsonResponse({'message': 'Files uploaded'})
    else:
        response = JsonResponse({'message': 'No files or path or branch received'})
    return response

@require_http_methods(["POST", "OPTIONS"])
@permissions.requires_permission_to("write")
@uploads.add_handlers
# @notification.notify("committed to")
#@notification.activity("committed")
@errors.catch
def delete_files(request, user, project_name, permissions_token=None):

    post = json.loads(request.body)
    repo = fetch_repository(user, project_name)
    email = post.get('email', 'git@wevolver.com')
    message = post.get('commit_message', 'deleted files')
    name = post.get('user_name', user)
    branch = request.GET.get('branch') if request.GET.get('branch') else 'master'
    files = post.get('files', None)
    if files:
        new_commit_tree = porcelain.remove_files_by_path(repo, branch, files.split(','))
        porcelain.commit_tree(repo, branch, new_commit_tree, name, email, message)
        response = JsonResponse({'message': 'Files Deleted'})
    else:
        response = JsonResponse({'message': 'No Files Deleted'})
    response['Permissions'] = permissions_token
    return response

@require_http_methods(["GET", "OPTIONS"])
@permissions.requires_permission_to('read')
@errors.catch
def list_bom(request, user, project_name, permissions_token):
    """ Collects all the bom.csv files in a repository and return their sum.

        Flattens the repository's tree into an array. Then filters the array for 'bom.csv',
        concatenates them and returns unique lines.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        HttpResponse: The full Bill of Materials (BOM)
    """

    branch = request.GET.get('branch') if request.GET.get('branch') else 'master'
    repo = fetch_repository(user, project_name)
    tree = (repo.revparse_single(branch).tree)
    blobs = porcelain.flatten(tree, repo)
    data = ''
    for b in [blob for blob in blobs if blob.name == 'bom.csv']:
        data += str(repo[b.id].data, 'utf-8')
    response = HttpResponse(data)
    return response

@require_http_methods(["GET", "OPTIONS"])
@permissions.requires_permission_to('read')
@errors.catch
def list_branches(request, user, project_name, permissions_token):
    """ Collects and returns all the names of the branches from the repository.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        JsonResponse: The list of branches
    """

    repo = fetch_repository(user, project_name)
    branch = request.GET.get('branch') if request.GET.get('branch') else 'master'
    branches = {'branches': [repo for repo in repo.branches]}
    response = JsonResponse(branches)
    return response

@require_http_methods(["GET", "OPTIONS"])
@permissions.requires_permission_to('read')
@errors.catch
def list_branches_ahead_behind(request, user, project_name, permissions_token):
    """ Returns the number of commits each branch is ahead or behind master

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        JsonResponse: The list of branches and their status
    """
    repo = fetch_repository(user, project_name)
    branches = []
    for branch in repo.branches:
        branch_latest_commit_oid = repo.lookup_branch(branch).target;
        ahead, behind = repo.ahead_behind(branch_latest_commit_oid.hex, repo.lookup_branch('master').target.hex)
        branchParams = {
            'name': branch,
            'ahead': ahead,
            'behind': behind,
            'commit_time': repo.get(branch_latest_commit_oid).commit_time
        }
        branches.append(branchParams)
    response = JsonResponse({ 'branches': branches })
    return response

@require_http_methods(["GET", "OPTIONS"])
@permissions.requires_permission_to('read')
@errors.catch
def download_archive(request, user, project_name, permissions_token):
    """ Grabs and returns a user's repository as a tarball.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.

    Returns:
        JsonResponse: An object with the requested user's repository as a tarball.
    """
    branch = request.GET.get('branch', 'master')
    filename = project_name + '.tar'
    response = HttpResponse(content_type='application/x-gzip')
    response['Content-Disposition'] = 'attachment; filename=' + filename
    repo = fetch_repository(user, project_name)
    with tarfile.open(fileobj=response, mode='w') as archive:
        repo.write_archive(repo.revparse_single(branch).id, archive)
    return response

@require_http_methods(["GET", "OPTIONS"])
@permissions.requires_permission_to('read')
@errors.catch
def read_history(request, user, project_name, permissions_token):
    """ Grabs and returns the history of a single file.

       The commit history of the branch is parsed and the file of
       interest is found on each commit tree.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        JsonResponse: The history of the file at this path.
    """

    path = request.GET.get('path').rstrip('/').lstrip('/')
    branch = request.GET.get('branch') if request.GET.get('branch') else 'master'
    history_type = request.GET.get('type')
    repo = fetch_repository(user, project_name)
    root_tree = repo.revparse_single(branch).tree
    git_tree, git_blob, folder_path = porcelain.walk_tree(repo, root_tree, path)
    page_size = int(request.GET.get('page_size', 10))
    page = int(request.GET.get('page', 0))
    start_index = page_size * page
    history = []

    if page_size == 1 and page == 0:
        lastCommit = repo[repo.head.target]
        history = [{
            'author': lastCommit.author.email,
            'committer': lastCommit.committer.email,
            'committer_name': lastCommit.committer.name,
            'commit_description': '',
            'commit_title': '',
            'commit_time': lastCommit.commit_time,
            'commit_id': lastCommit.id.__str__(),
            'commit_files': [],
        }]
        return JsonResponse({'history': history})

    for commit in itertools.islice(repo.walk(repo.revparse_single(branch).id, GIT_SORT_TIME), start_index,  start_index + page_size + 1):
        try:
            title, description = split_commit_message(commit.message)
        except:
            title, description = commit.message, None
        if history_type == 'file':
            git_tree, git_blob, folder_path = porcelain.walk_tree(repo, commit.tree, path)
            if len(commit.parents) > 0:
                try:
                    diff = repo.diff(commit.tree, commit.parents[0].tree)
                    if type(git_blob) == pygit2.Blob and any(patch.delta.new_file.path == path for patch in diff):
                        history.append({
                            'id': git_blob.id.__str__(),
                            'commit_time': commit.commit_time,
                            'commit_description': description,
                            'commit_id': commit.id.__str__(),
                            'committer': commit.committer.email,
                            'committer_name': commit.committer.name,
                            'commit_title': title,
                        })
                except:
                    print('Failed to load history')
        elif history_type == 'commits':
            # Commit tree diff
            try:
                diff = repo.diff(commit.tree, commit.parents[0].tree)
                files = []
                for patch in diff:
                    # status: 1 deleted, 2 added, 3 modified
                    files.append({'path': patch.delta.new_file.path, 'status': patch.delta.status})
            except:
                files = []
            history.append({
                'author': commit.author.email,
                'committer': commit.committer.email,
                'committer_name': commit.committer.name,
                'commit_description': description,
                'commit_title': title,
                'commit_time': commit.commit_time,
                'commit_id': commit.id.__str__(),
                'commit_files': files,
            })
    return JsonResponse({'history': history})

@require_http_methods(["GET", "OPTIONS"])
@permissions.requires_permission_to('read')
@errors.catch
def read_tree(request, user, project_name, permissions_token):
    """ Grabs and returns a single file or a tree from a user's repository

        The requested tree is first parsed into JSON.

    Args:
        user (string): The user's name.
        project_name (string): The user's repository name.
        permissions_token (string): JWT token signed by Wevolver.

    Returns:
        JsonResponse: An object with the requested tree as JSON
    """
    repo = fetch_repository(user, project_name)
    path = request.GET.get('path').rstrip('/').lstrip('/')
    branch = request.GET.get('branch') if request.GET.get('branch') else 'master'
    root_tree = repo.revparse_single(branch).tree
    parsed_tree = None
    parsed_tree = porcelain.parse_full_tree(repo, root_tree)
    lastCommit = repo[repo.head.target]
    lastCommitTime = lastCommit.commit_time

    response = JsonResponse({'tree': parsed_tree, 'lastCommitTime': lastCommitTime})
    response['Permissions'] = permissions_token
    return response

@require_http_methods(["POST", "OPTIONS"])
@permissions.requires_permission_to('write')
#@notification.activity("committed")
@errors.catch
def revert_commit(request, user, project_name, permissions_token=None):
    repo = fetch_repository(user, project_name)
    branch = request.GET.get('branch') if request.GET.get('branch') else 'master'
    email = request.POST.get('email', 'git@wevolver.com')
    message = request.POST.get('commit_message', repo.get(branch).message)
    name = request.POST.get('user_name', user)
    new_commit_tree = porcelain.add_blobs_to_tree(repo, branch, [])
    porcelain.commit_tree(repo, 'master', new_commit_tree, name, email, message)
    response = JsonResponse({'message':'success'})
    return response
