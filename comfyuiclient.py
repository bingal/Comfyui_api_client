import io
import sys
import uuid
import json
import time
import random
import urllib.request
import urllib.parse
import requests
import aiohttp
from PIL import Image
from requests.auth import HTTPBasicAuth

class ComfyUIClientAsync:

    def __init__(self, url, prompt_file, username=None, password=None):
        self.PROMPT_FILE = prompt_file
        self.SERVER_ADDRESS = url[:-1] if url.endswith('/') else url
        self.CLIENT_ID = str(uuid.uuid4())
        self.ws = None
        self.session = None
        self.auth = HTTPBasicAuth(username, password) if username and password else None

        with open(self.PROMPT_FILE, 'r', encoding='utf8') as f:
            self.comfyui_prompt = json.loads(f.read())

    async def connect(self):
        self.session = aiohttp.ClientSession(auth=self.auth)
        ws_protocol = "wss" if self.SERVER_ADDRESS.startswith("https") else "ws"
        ws_url = f"{ws_protocol}://{self.SERVER_ADDRESS.split('//')[-1]}/ws?clientId={self.CLIENT_ID}"
        self.ws = await self.session.ws_connect(ws_url)

    async def close(self):
        await self.ws.close()
        await self.session.close()

    async def queue_prompt(self, prompt):
        payload = {"prompt": prompt, "client_id": self.CLIENT_ID}
        data = json.dumps(payload).encode('utf-8')
        async with self.session.post(f"{self.SERVER_ADDRESS}/prompt", data=data) as response:
            return await response.json()

    async def get_image(self, filename, subfolder, folder_type):
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(params)
        async with self.session.get(f"{self.SERVER_ADDRESS}/view?{url_values}") as response:
            return await response.read()

    async def get_history(self, prompt_id):
        async with self.session.get(f"{self.SERVER_ADDRESS}/history/{prompt_id}") as response:
            return await response.json()

    async def get_images(self, prompt):
        prompt_id = (await self.queue_prompt(prompt))['prompt_id']
        output_images = {}
        while True:
            message = await self.ws.receive()
            if message.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(message.data)
                if data['type'] == 'executing' and data['data']['node'] is None and data['data']['prompt_id'] == prompt_id:
                    break
        
        history = (await self.get_history(prompt_id))[prompt_id]
        for node_id, node_output in history['outputs'].items():
            images_output = []
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = await self.get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output
        
        return output_images
    
    def set_data(self, key, text:str=None, seed:int=None, image:Image.Image=None):
        key_id = self.find_key_by_title(key)
        if text is not None:
            self.comfyui_prompt[key_id]['inputs']['text'] = text
        if seed is not None:
            self.comfyui_prompt[key_id]['inputs']['seed'] = int(seed)
        if image is not None:
            # Upload image to comfyui server
            folder_name = "temp"
            
            # Save image to byte data
            byte_data = io.BytesIO()
            image.save(byte_data, format="PNG")
            byte_data.seek(0)

            # Upload image
            resp = requests.post(
                f"{self.SERVER_ADDRESS}/upload/image", 
                files={'image': ("temp.png", byte_data)}, 
                data={"subfolder": folder_name},
                auth=self.auth)
            
            # Set image path
            resp_json = json.loads(resp.content.decode('utf-8'))
            self.comfyui_prompt[key_id]['inputs']['image'] = resp_json.get('subfolder') + '/' + resp_json.get('name')

    def find_key_by_title(self, target_title):
        target_title = target_title.strip()
        for key, value in self.comfyui_prompt.items():
            title = value.get('_meta', {}).get('title', '').strip()
            if title == target_title:
                return key
        print(f"Key not found: {target_title}")
        return None

    async def generate(self, node_names=None) -> dict:
        node_ids = {}
        if node_names is not None:
            for node_name in node_names:
                node_id = self.find_key_by_title(node_name)
                if node_id is not None:
                    node_ids[node_id] = node_name

        images = await self.get_images(self.comfyui_prompt)
        results = {}
        for node_id, node_images in images.items():
            if node_id in node_ids:
                for image_data in node_images:
                    image = Image.open(io.BytesIO(image_data))
                    results[node_ids[node_id]] = image

        return results


class ComfyUIClient:

    def __init__(self, url, prompt_file, username=None, password=None):
        self.PROMPT_FILE = prompt_file
        self.SERVER_ADDRESS = url
        self.CLIENT_ID = str(uuid.uuid4())
        self.session = None
        self.auth = HTTPBasicAuth(username, password) if username and password else None

        with open(self.PROMPT_FILE, 'r', encoding='utf8') as f:
            self.comfyui_prompt = json.loads(f.read())

    def connect(self):
        self.session = requests.Session()
        ws_protocol = "wss" if self.SERVER_ADDRESS.startswith("https") else "ws"
        ws_url = f"{ws_protocol}://{self.SERVER_ADDRESS.split('//')[-1]}/ws?clientId={self.CLIENT_ID}"
        self.session.get(ws_url, auth=self.auth)

    def close(self):
        if self.session is not None:
            self.session.close()
            self.session = None

    def queue_prompt(self, prompt):
        payload = {"prompt": prompt, "client_id": self.CLIENT_ID}
        data = json.dumps(payload).encode('utf-8')
        response = self.session.post(f"{self.SERVER_ADDRESS}/prompt", data=data, auth=self.auth)
        return response.json()

    def get_image(self, filename, subfolder, folder_type):
        params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(params)
        response = self.session.get(f"{self.SERVER_ADDRESS}/view?{url_values}", auth=self.auth)
        return response.content

    def get_history(self, prompt_id):
        response = self.session.get(f"{self.SERVER_ADDRESS}/history/{prompt_id}", auth=self.auth)
        return response.json()

    def get_images(self, prompt):
        prompt_id = self.queue_prompt(prompt).get('prompt_id')
        output_images = {}

        while True:
            history = self.get_history(prompt_id)
            if prompt_id in history and 'outputs' in history[prompt_id]:
                break
            time.sleep(1)
        
        for node_id, node_output in history[prompt_id]['outputs'].items():
            images_output = []
            if 'images' in node_output:
                for image in node_output['images']:
                    image_data = self.get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output
        
        return output_images
    
    def set_data(self, key, text:str=None, seed:int=None, image:Image.Image=None):
        key_id = self.find_key_by_title(key)
        if text is not None:
            self.comfyui_prompt[key_id]['inputs']['text'] = text
        if seed is not None:
            self.comfyui_prompt[key_id]['inputs']['seed'] = int(seed)
        if image is not None:
            # Upload image to comfyui server
            folder_name = "temp"
            
            # Save image to byte data
            byte_data = io.BytesIO()
            image.save(byte_data, format="PNG")
            byte_data.seek(0)

            # Upload image
            resp = self.session.post(
                f"{self.SERVER_ADDRESS}/upload/image", 
                files={'image': ("temp.png", byte_data)}, 
                data={"subfolder": folder_name},
                auth=self.auth)
            
            # Set image path
            resp_json = json.loads(resp.content.decode('utf-8'))
            self.comfyui_prompt[key_id]['inputs']['image'] = resp_json.get('subfolder') + '/' + resp_json.get('name')

    def find_key_by_title(self, target_title):
        target_title = target_title.strip()
        for key, value in self.comfyui_prompt.items():
            title = value.get('_meta', {}).get('title', '').strip()
            if title == target_title:
                return key
        print(f"Key not found: {target_title}")
        return None

    def generate(self, node_names=None) -> dict:
        node_ids = {}
        if node_names is not None:
            for node_name in node_names:
                node_id = self.find_key_by_title(node_name)
                if node_id is not None:
                    node_ids[node_id] = node_name

        images = self.get_images(self.comfyui_prompt)
        results = {}
        for node_id, node_images in images.items():
            if node_id in node_ids:
                for image_data in node_images:
                    image = Image.open(io.BytesIO(image_data))
                    results[node_ids[node_id]] = image

        return results


def main():
    print("Starting comfyui client")
    
    comfyui_client = None
    try:
        comfyui_client = ComfyUIClient("http://127.0.0.1:8188", "workflow_api.json")
        # If you need to authenticate, you can use the following code
        # comfyui_client = ComfyUIClientAsync("http://127.0.0.1:8188", "workflow_api.json", username="user", password="password")
        comfyui_client.connect()
        comfyui_client.set_data(key='KSampler', seed=random.randint(0, sys.maxsize))
        comfyui_client.set_data(key='CLIP Text Encode Positive', text="beautiful landscape painting")
        # If you need to upload an image, you can use the following code `from PIL import Image`
        # comfyui_client.set_data(key='KSampler', comfyui_client.set_data(key='Load Image', image=Image.open('input_image.png')))
        for key, image in comfyui_client.generate(["Result Image"]).items():
            image.save(f"{key}.png")
            print(f"Saved {key}.png")
    finally:
        if comfyui_client is not None:
            comfyui_client.close()


async def main_async():
    print("Starting comfyui client (async)")
    
    comfyui_client = None
    try:
        comfyui_client = ComfyUIClientAsync("http://127.0.0.1:8188", "workflow_api.json")
        # If you need to authenticate, you can use the following code
        # comfyui_client = ComfyUIClientAsync("http://127.0.0.1:8188", "workflow_api.json", username="user", password="password")
        await comfyui_client.connect()
        comfyui_client.set_data(key='KSampler', seed=random.randint(0, sys.maxsize))
        comfyui_client.set_data(key='CLIP Text Encode Positive', text="beautiful landscape painting")
        # If you need to upload an image, you can use the following code `from PIL import Image`
        # comfyui_client.set_data(key='KSampler', comfyui_client.set_data(key='Load Image', image=Image.open('input_image.png')))
        for key, image in (await comfyui_client.generate(["Result Image"])).items():
            image.save(f"{key}_async.png")
            print(f"Saved {key}_async.png")
    finally:
        if comfyui_client is not None:
            await comfyui_client.close()


if __name__ == "__main__":
    # non-async
    main()

    # async
    import asyncio
    asyncio.run(main_async())
