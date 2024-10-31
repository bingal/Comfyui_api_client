# Comfyui_api_client
This is a class that makes it easier to send data to the ComfyUI API.

There are two versions: the regular version (`ComfyUiClient`) and the async version (`ComfyUiClientAsync`).

A key feature is the `set_data` method, which automatically finds the node name and inserts the data.

For example, if there is a node titled "CLIP Text Encode Positive" and you want to insert text into its text part:

```python
comfyui_client.set_data(key='CLIP Text Encode Positive', text="beautiful landscape painting")
```

By specifying this, you can insert text into the text part of the corresponding node.

The `set_data` method accepts multiple arguments: `text`, `seed`, and `image`. The `image` argument accepts a `PIL.Image` type image, uploads it to the server, and sets the parameter. This is intended for use with the Load Image node.

```python
comfyui_client.set_data(key='Load Image', image=Image.open(input_image_file))
```

To save the generated image:

```python
comfyui_client.generate(["Result Image"])
```

By specifying the node names as an array in this `generate` method, you can retrieve the images.

Therefore, when creating a workflow, you need to give the nodes you want to retrieve images from unique and easily recognizable names.

The return value is a pair of node names and images (`PIL.Image`), so you can process them as needed.

# Sample

```python
comfyui_client = None
try:
    comfyui_client = ComfyUIClient("127.0.0.1:8188", "workflow_api.json")
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
```

# Sample Async

```python
comfyui_client = None
try:
    comfyui_client = ComfyUIClientAsync("127.0.0.1:8188", "workflow_api.json")
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
```
