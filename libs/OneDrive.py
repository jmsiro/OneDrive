import requests
import json
import os


class OneDrive:
    def __init__(self, *, client_id, client_secret, tenant, redirect_uri, path_credentials):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = 'files.readwrite.all offline_access'
        self.redirect_uri = redirect_uri
        self.tenant = tenant
        self.access_token = None
        self.refresh_token = None
        self.path_credentials = path_credentials

    def get_token(self, auth_code, grant_type):
        """ Get the access_token or refresh_token.

        The token that is obtained depends if it is the first time that the user is authenticated or not.

        Parameters
        ----------
        auth_code : dict
            Contains code or refresh_token
        grant_type : str
            Type of grant_type, it could be code or refresh_token

        Returns
        -------
        dict
            a json with the credentials
        """

        url, params = self.build_request(auth_code, grant_type)
        response = requests.post(url, data=params)
        json_response = json.loads(response.text)
        self.access_token = json_response['access_token']
        new_refresh_token = json_response['refresh_token']
        self.refresh_token = new_refresh_token
        return json_response

    def build_request(self, auth_code, grant_type):
        """ Build the request.

        It depends if it is access_token or refresh_token.

        Parameters
        ----------
        auth_code : dict
            Contains code or refresh_token
        grant_type : str
            Type of grant_type, it could be code or refresh_token

        Returns
        -------
        string, dict
            a formed url and a dict with parameters

        """

        params = {
            'client_id': self.client_id,
            'scope': self.scope,
            'redirect_uri': self.redirect_uri,
            'grant_type': grant_type,
            'client_secret': self.client_secret,
        }
        params.update(auth_code)
        url = 'https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token'.format(tenant=self.tenant)
        return url, params

    def create_tokens_file(self, credentials):
        """ Create a json with credentials.

        Create a json with credentials.

        Parameters
        ----------
        credentials : dict
            Contains the credentials

        """

        try:
            with open(self.path_credentials, 'w') as credfile:
                json.dump(credentials, credfile)
            return True
        except Exception as e:
            print(e)
            raise e

    def get_items(self):
        """ List children in the root of the current user's drive.

        Create a json with credentials.

        Returns
        -------
        dict
            folders in root
        """
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
        response = requests.get(url, headers=headers)
        json_response = json.loads(response.text)
        return json_response
    
    def get_items_shared_with_me(self):
        """ List items shred to the current user's drive.

        Create a json with credentials.

        Returns
        -------
        dict
            shared items
        """
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        url = "https://graph.microsoft.com/v1.0/me/drive/sharedWithMe"
        response = requests.get(url, headers=headers)
        json_response = json.loads(response.text)
        return json_response

    def list_items(self, item_id):
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        url = "https://graph.microsoft.com/v1.0//me/drive/items/{item_id}/children".format(item_id=item_id)
        response = requests.get(url, headers=headers)
        json_response = json.loads(response.text)
        return json_response

    def download_item(self, item_id, folder_path):
        headers = {
            'Authorization': 'Bearer ' + self.access_token
        }
        url = "https://graph.microsoft.com/v1.0//me/drive/items/{item_id}/".format(item_id=item_id)
        response = requests.get(url, headers=headers)
        json_response = json.loads(response.text)
        url_download = json_response['@microsoft.graph.downloadUrl']
        filename = json_response['name']
        response_download = requests.get(url_download, headers=headers)
        # print(response_download.json())
        
        if not response_download:
            return False

        with open(folder_path + os.sep + filename, 'wb') as file:
            file.write(response_download.content)
        return True

    def upload_item(self, file_path, drive_id, folder_path, conflict):
        headers = {
            'Authorization': 'Bearer ' + self.access_token,
            'Content-Type': 'application/json'
        }
        # Before uploading it is necessary to open the file in binary for reading

        filename = file_path.split("/")[-1]
 
        total_file_size = os.path.getsize(file_path)
        if total_file_size > 4000000:
            
            body = {
                "item": {
                    "@microsoft.graph.conflictBehavior": conflict,
                    "name": filename
                }
            }
                       
            upload_session = requests.post(f"https://graph.microsoft.com/v1.0/me/drive/items/{drive_id}:/{folder_path}{filename}:/createUploadSession", headers=headers, json=body).json()
            
            try:
                with open(file_path, 'rb') as f: 
                    chunk_size = 327680
                    chunk_number = total_file_size // chunk_size
                    chunk_leftover = total_file_size - chunk_size * chunk_number
                    i = 0
                    while True:
                        chunk_data = f.read(chunk_size)
                        start_index = i*chunk_size
                        end_index = start_index + chunk_size
                        #If end of file, break
                        if not chunk_data:
                            break
                        if i == chunk_number:
                            end_index = start_index + chunk_leftover
                        #Setting the header with the appropriate chunk data location in the file
                        headers_session = {
                            'Content-Length': f'{chunk_size}',
                            'Content-Range': f'bytes {start_index}-{end_index-1}/{total_file_size}'
                            }
                        #Upload one chunk at a time
                        chunk_data_upload = requests.put(upload_session['uploadUrl'], data=chunk_data, headers=headers_session)
                        
                        if 'createdBy' in chunk_data_upload.json():
                            print("File upload compete")
                            return chunk_data_upload.json()
                        else:
                            print(f"File upload progress: {chunk_data_upload.json()}")
                        i = i + 1
                return chunk_data_upload.json()
            except KeyError:
                return upload_session
        else:
            with open(file_path, "rb") as file:
                fileHandle = file.read()
            
            resolution = f"?@microsoft.graph.conflictBehavior={conflict}"
                        
            url = f"https://graph.microsoft.com/v1.0/me/drive/items/{drive_id}:/{folder_path}{filename}:/content{resolution}"
            response = requests.put(url, data=fileHandle, headers=headers)
            
            return response.json()
    
    def delete_item(self, item_id):
        """ Moves this item to the Recycle Bin

        :return: Success / Failure
        :rtype: bool
        """
        headers = {
            'Authorization': 'Bearer ' + self.access_token,
        }
        
        url = "https://graph.microsoft.com/v1.0/me/drive/items/{item_id}".format(
            item_id=item_id)
        
        response = requests.delete(url, headers=headers)
        
        if not response:
            return False

        return True
        
    def move_item(self, item_id, target_id):
        """ Moves this DriveItem to another Folder.
        Can't move between different Drives.

        :param target: a Folder, Drive item or Item Id string.
         If it's a drive the item will be moved to the root folder.
        :type target: drive.Folder or DriveItem or str
        :return: Success / Failure
        :rtype: bool
        """
        
        headers = {
            'Authorization': 'Bearer ' + self.access_token,
        }
        
        url = "https://graph.microsoft.com/v1.0/me/drive/items/{item_id}".format(
            item_id=item_id)
        
        # if isinstance(target, Folder):
        #     target_id = target.object_id
        # elif isinstance(target, Drive):
        #     # we need the root folder id
        #     root_folder = target.get_root_folder()
        #     if not root_folder:
        #         return False
        #     target_id = root_folder.object_id
        # elif isinstance(target, str):
        #     target_id = target
        # else:
        #     raise ValueError('Target must be a Folder or Drive')

        # if not self.object_id or not target_id:
        #     raise ValueError(
        #         'Both self, and target must have a valid object_id.')

        if target_id == 'root':
            raise ValueError("When moving, target id can't be 'root'")

        # url = self.build_url(
        #     self._endpoints.get('item').format(id=self.object_id))

        payload = {"parentReference": {"id": "{target_id}".format(target_id=target_id)}}
        
        response = requests.patch(url, json=payload, headers=headers)
        
        if not response:
            return False

        return True
