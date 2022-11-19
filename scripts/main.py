import gradio as gr
from modules import script_callbacks
import modules.ui
import modules.generation_parameters_copypaste as parameters_copypaste

# -- start of ultility classes --
import os
import requests
from io import BytesIO
from PIL import Image, ImageEnhance, ImageColor
from rembg import remove
import numpy as np

class ImageHandler:
  def __init__(self, im = None, url = None, file_path = None):
    self._im = None
    if im:
      self._im = im
    elif url:
      self.fetch_from_url(url, file_path)
    elif file_path:
      self.fetch_from_path(file_path)    
    
  def fetch_from_url(self, url, path_to_store = None):
    im = Image.open(BytesIO(requests.get(url).content))
    if path_to_store:
      im.save(path_to_store)
    self._im = im

  def fetch_from_path(self, file_path):
    im = Image.open(file_path)
    self._im = im
  
  def resize(self, width, height, preserve_aspect_ratio = True):
    if preserve_aspect_ratio:
      self._im.thumbnail((width,height))
    else:
      self._im=self._im.resize((width,height))
  
  def enhance(self, 
                greyscale_factor = None, 
                contrast_factor = None,
                brightness_factor = None,
                sharpness_factor = None):
    if greyscale_factor:
      enhancer = ImageEnhance.Color(self._im)
      self._im=enhancer.enhance(greyscale_factor)
    if contrast_factor:
      enhancer = ImageEnhance.Contrast(self._im)
      self._im=enhancer.enhance(contrast_factor)
    if brightness_factor:
      enhancer = ImageEnhance.Brightness(self._im)
      self._im=enhancer.enhance(brightness_factor)
    if sharpness_factor:
      enhancer = ImageEnhance.Sharpness(self._im)
      self._im=enhancer.enhance(sharpness_factor)

  def remove_background(self):
    self._im = remove(self._im)

  def add_background(self,
                     bg_img,
                     size_of_object_to_background = None,
                     position_of_object_to_left = None,
                     position_of_object_to_top = None,
                     change_background_to_color_rbga = None,
                     ):
    (obj_width, obj_height) = self._im.size
    (bg_width, bg_height) = bg_img.size

    self._im = self._im.convert('RGBA')
    bg_img = bg_img.convert('RGBA')

    if change_background_to_color_rbga:
      bg_img = Image.new(mode='RGBA', size=(bg_width, bg_height), color=change_background_to_color_rbga)

    if size_of_object_to_background:
      (obj_width, obj_height) = (bg_width * size_of_object_to_background, bg_height * size_of_object_to_background)
      self.resize(obj_width, obj_height)
    position = (0, 0)
    if position_of_object_to_left and position_of_object_to_top:
      left_pos = int(bg_width * position_of_object_to_left - 0.5 * obj_width)
      upper_pos = int(bg_height * position_of_object_to_top - 0.5 * obj_height)
      position = (left_pos, upper_pos)

    bg_img.paste(
        self._im, 
        position, 
        mask = self._im)
    self._im = bg_img

  def convert_to_mask(self, sharpness_filter = 25):
    rgba = np.array(self._im.convert('RGBA'))
    rgba[rgba[...,-1]<=sharpness_filter] = [255,255,255,0]
    rgba[rgba[...,-1]>sharpness_filter] = [0,0,0,255]
    self._im = Image.fromarray(rgba)

  def image(self):
    return self._im

  def copy(self):
    return ImageHandler(im = self._im.copy())
  
  def save(self, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok = True)
    self._im.save(file_path)

# -- end of ultility classes --
  


def remove_background_gen_mask(object_img, mask_sharpness_filter):
    im_handler = ImageHandler(im = object_img)
    
    im_handler.remove_background()
    # create mask
    mask_im_handler = im_handler.copy()
    mask_im_handler.convert_to_mask(sharpness_filter = mask_sharpness_filter)
    
    return im_handler.image(), mask_im_handler.image()

def add_new_background_gen_mask(
  object_bg_removed_img, 
  bg_img, 
  mask_sharpness_filter,
  size_of_object_to_background,
  position_of_object_to_left,
  position_of_object_to_top,
  use_solid_color_bg,
  change_background_to_color_rbga
):
    im_handler = ImageHandler(im = object_bg_removed_img)
    mask_im_handler = im_handler.copy()

    if use_solid_color_bg:
      solid_color_bg = change_background_to_color_rbga
    else:
      solid_color_bg = None
    
    # add background
    im_handler.add_background(bg_img.copy(), size_of_object_to_background, position_of_object_to_left, position_of_object_to_top, solid_color_bg)

    # make is transparent
    mask_im_handler.add_background(bg_img.copy(), size_of_object_to_background, position_of_object_to_left, position_of_object_to_top, (255, 255, 255, 0))

    # create mask
    mask_im_handler.convert_to_mask(sharpness_filter = mask_sharpness_filter)

    return im_handler.image(), mask_im_handler.image()

def on_ui_tabs():
    with gr.Blocks() as x_interface:
      (
          init_img_with_mask,
          init_img_inpaint, 
          init_mask_inpaint, 
          mask_mode
      ) = (
          modules.ui.img2img_paste_fields[15][0], 
          modules.ui.img2img_paste_fields[16][0], 
          modules.ui.img2img_paste_fields[17][0],
          modules.ui.img2img_paste_fields[18][0]
          )
      with gr.Tab("Remove Background"):
          with gr.Row():
            with gr.Column():
              rb_object_img = gr.Image(label="Object Image", show_label=True, source="upload", interactive=True, type="pil", image_mode='RGBA', tool = 'color-sketch')
              rb_mask_sharpness_filter = gr.Slider(minimum=0, maximum=255, step=1, label="Mask Sharpness Filter", value=25)
              rb_process_button = gr.Button('Go')
            with gr.Column():
                rb_ret_img = gr.Image(label='Background removed object', show_label=True, interactive=False, type="pil", image_mode='RGBA')
                rb_mask_img = gr.Image(label='Mask', show_label=True, interactive=False, type="pil", image_mode='RGBA')
                
                rb_inpaint_button = gr.Button('Send to Inpaint')
                rb_send_buttons = parameters_copypaste.create_buttons(["img2img", "extras"])

                rb_process_button.click(
                    fn=remove_background_gen_mask,
                    inputs=[rb_object_img, rb_mask_sharpness_filter],
                    outputs=[rb_ret_img, rb_mask_img]
                )

                rb_inpaint_button.click(
                    lambda *x: x, 
                    inputs=[rb_object_img, rb_object_img, rb_mask_img], 
                    outputs=[init_img_with_mask, init_img_inpaint, init_mask_inpaint])

                rb_inpaint_button.click(
                    fn=None,
                    _js=f"switch_to_inpaint",
                    inputs=None,
                    outputs=None,
                )
                parameters_copypaste.bind_buttons(rb_send_buttons, rb_object_img, None)

      with gr.Tab("Add New Background"):
          with gr.Row():
            with gr.Column():
              anb_object_img = gr.Image(label="Background Removed Object Image", show_label=True, source="upload", interactive=True, type="pil", image_mode='RGBA')
              anb_get_object_button = gr.Button('Get Object Image from Previous Step')
              anb_bg_img = gr.Image(label="Background Image", show_label=True, source="upload", interactive=True, type="pil", image_mode='RGBA')
              
              anb_mask_sharpness_filter = gr.Slider(minimum=0, maximum=255, step=1, label="Mask Sharpness Filter", value=25)
              size_of_object_to_background = gr.Slider(label="Size of Object to Background", minimum=0, maximum=1.0, step=0.1, value=0.5)
              position_of_object_to_left = gr.Slider(label="Position of Object to Left", minimum=0, maximum=1.0, step=0.1, value=0.5)
              position_of_object_to_top = gr.Slider(label="Position of Object to Top", minimum=0, maximum=1.0, step=0.1, value=0.7)

              with gr.Row():
                use_solid_color_bg = gr.Checkbox(label='Use a solid color as background', value=False)
                change_background_to_color_rbga = gr.ColorPicker(label="Background Color", interactive=True)
              
              
              anb_process_button = gr.Button('Go')
            with gr.Column():
                anb_ret_img = gr.Image(label='Object with new background', show_label=True, interactive=False, type="pil", image_mode='RGBA')
                anb_mask_img = gr.Image(label='Mask', show_label=True, interactive=False, type="pil", image_mode='RGBA')
                
                anb_inpaint_button = gr.Button('Send to Inpaint')
                anb_send_buttons = parameters_copypaste.create_buttons(["img2img", "extras"])

                anb_get_object_button.click(
                    lambda x: x, 
                    inputs=[rb_ret_img], 
                    outputs=[anb_object_img]                  
                )

                anb_process_button.click(
                    fn=add_new_background_gen_mask,
                    inputs=[
                      anb_object_img, 
                      anb_bg_img, 
                      anb_mask_sharpness_filter,
                      size_of_object_to_background,
                      position_of_object_to_left,
                      position_of_object_to_top,
                      use_solid_color_bg,
                      change_background_to_color_rbga
                      ],
                    outputs=[anb_ret_img, anb_mask_img]
                )

                anb_inpaint_button.click(
                    lambda *x: x, 
                    inputs=[anb_ret_img, anb_ret_img, anb_mask_img], 
                    outputs=[init_img_with_mask, init_img_inpaint, init_mask_inpaint])

                anb_inpaint_button.click(
                    fn=None,
                    _js=f"switch_to_inpaint",
                    inputs=None,
                    outputs=None,
                )
                parameters_copypaste.bind_buttons(anb_send_buttons, anb_ret_img, None)

    return (x_interface, "X", "x"),


script_callbacks.on_ui_tabs(on_ui_tabs)
