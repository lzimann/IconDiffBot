import os
import re
import hmac
import json
from hashlib import sha1
import requests
from twisted.web import resource, server
from twisted.internet import reactor, endpoints

import icons

config = {}
if os.path.exists(os.path.abspath('config.json')):
    with open('config.json', 'r') as f:
        config = json.load(f)
else:
    print("Make sure the config file exists.")

github_secret = config['github']['secret'].encode('utf-8')
github_user = config['github']['user']
github_auth = config['github']['auth']
actions_to_check = ['opened', 'synchronize']
binary_regex = re.compile('diff --git a\/(.*\.dmi) b\/.?')

upload_api_url = config['upload_api']['url']
upload_api_key = config['upload_api']['key']

def compare_secret(secret_to_compare, payload):
    """fuck you"""
    if secret_to_compare is None:
        return False
   
    this_secret = hmac.new(github_secret, payload, sha1)
    secret_to_compare = secret_to_compare.replace('sha1=', '')
    return hmac.compare_digest(secret_to_compare, this_secret.hexdigest())

def check_diff(diff_url):
    """checks the diff url for icons"""
    req = requests.get(diff_url)
    if req.status_code == 404:
        return None
    diff = req.text.split('\n')
    icons_with_diff = []
    for line in diff:
        match = binary_regex.search(line)
        if not match:
            continue
        icons_with_diff.append(match.group(1))
    return icons_with_diff

def check_icons(icons_with_diff, base, head, issue_url, send_message = True):
    if not os.path.exists('./icon_dump'):
        os.makedirs('./icon_dump')
    icon_path_a = './icon_dump/old.dmi'
    icon_path_b = './icon_dump/new.dmi'
    base_repo_url = base.get('repo').get('html_url')
    head_repo_url = head.get('repo').get('html_url')
    msgs = ["Icons with diff:"]
    for icon in icons_with_diff:
        response_a = requests.get('{}/blob/{}/{}'.format(base_repo_url, base.get('ref'), icon), data={'raw':  1})
        response_b = requests.get('{}/blob/{}/{}'.format(head_repo_url, head.get('ref'), icon), data={'raw':  1})
        if response_a.status_code == 200:
            with open(icon_path_a, 'wb') as f:
                f.write(response_a.content)
        elif response_a.status_code == 404:
            icon_path_a = None
        if response_b.status_code == 200:
            with open(icon_path_b, 'wb') as f:
                f.write(response_b.content)
        elif response_b.status_code == 404: #This means the file is being deleted, which does not interest us
            try:
                os.remove(icon_path_a)
                continue
            except OSError:
                continue
        this_dict = icons.compare_two_icon_files(icon_path_a, icon_path_b)
        if not this_dict:
            continue
        msg = ["<details><summary>{}</summary>\n".format(icon), "Key | Old | New | Status", "--- | --- | --- | ---"]
        for key in this_dict:
            status = this_dict[key].get("status")
            if status == 'no_check':
                continue
            path_a = './icon_dump/old_{}.png'.format(key)
            path_b = './icon_dump/new_{}.png'.format(key)
            img_a = this_dict[key].get('img_a')
            if img_a:
                img_a.save(path_a)
                with open(path_a, 'rb') as f:
                    url_a = "![{}]({})".format(key, requests.post(upload_api_url, data={'key' : upload_api_key}, files={'file' : f}).json().get('url'))
            else:
                url_a = "![]()"
            img_b = this_dict[key].get('img_b')
            if img_b:
                img_b.save(path_b)
                with open(path_b, 'rb') as f:
                    url_b = "![{}]({})".format(key, requests.post(upload_api_url, data={'key' : upload_api_key}, files={'file' : f}).json().get('url'))
            else:
                url_b = "![]()"
            if os.path.exists(path_a):
                os.remove(path_a)
            if os.path.exists(path_b):
                os.remove(path_b)

            msg.append("{key}|{url_a}|{url_b}|{status}".format(key=key, url_a=url_a, url_b=url_b, status=status))
        msg.append("</details>")
        msgs.append("\n".join(msg))
    if send_message:
        github_api_url = "{issue}/comments".format(issue=issue_url)
        if len(msgs) > 1:
            body = json.dumps({'body' : '\n'.join(msgs)})
            requests.post(github_api_url, data=body, auth=(github_user, github_auth))
    if os.path.exists(icon_path_a):
        os.remove(icon_path_a)
    if os.path.exists(icon_path_b):
        os.remove(icon_path_b)

class Handler(resource.Resource):
    isLeaf = True
    def render_POST(self, request):
        print("POST received.")
        payload = request.content.getvalue()
        if not compare_secret(request.getHeader('X-Hub-Signature'), payload):
            request.setResponseCode(401)
            return b"Secret does not match"
        if request.getHeader('X-GitHub-Event') != 'pull_request':
            request.setResponseCode(404)
            return b"Event not supported"

        #Then we check the PR for icon diffs
        payload = json.loads("".join(map(chr, payload)))
        request.setResponseCode(200)
        pr_obj = payload['pull_request']
        if payload['action'] not in actions_to_check:
            return b"Not actionable"
        issue_url = pr_obj['issue_url']
        pr_diff_url = pr_obj['diff_url']
        head = pr_obj['head']
        base = pr_obj['base']
        if payload['action'] == 'synchronize':
            pr_diff_url = "{html_url}/commits/{sha}.diff".format(html_url=pr_obj['html_url'], sha=head['sha'])
        icons_with_diff = check_diff(pr_diff_url)
        if icons_with_diff:
            print("Diff on PR {}!".format(payload['number']))
            check_icons(icons_with_diff, base, head, issue_url)
        return b"Ok"
    def render_GET(self, request):
        request.setResponseCode(666)
        return b"Fuck u"

def test_pr(number, send_message = False):
    """tests a pr for the icon diff"""
    req = requests.get("https://api.github.com/repos/tgstation/tgstation/pulls/{}".format(number))
    if req.status_code == 404:
        print("PR does not exist")
        return
    payload = req.json()
    icons = check_diff(payload['diff_url'])
    print("Icons:")
    print("\n".join(icons))
    check_icons(icons, payload['base'], payload['head'], payload['html_url'], send_message)

if __name__ == '__main__':
    endpoints.serverFromString(reactor, "tcp:{}".format(config['webhook_port'])).listen(server.Site(Handler()))
    try:
        print("Listening for requests on port: {}.".format(config['webhook_port']))
        reactor.run()
    except KeyboardInterrupt:
        pass
