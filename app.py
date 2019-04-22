import os
import sys
import scipy.io
import scipy.misc
import matplotlib.pyplot as plt
from matplotlib.pyplot import imshow
from PIL import Image
from nst_utils import *
import numpy as np
import tensorflow as tf
from multiprocessing import Process, Value
from azure.storage.blob import BlockBlobService, PublicAccess
from azure.storage.queue import QueueService, QueueMessage, QueueMessageFormat
import base64
import json
import urllib.request
from flask import Flask, request, Response, send_file
queue_service = QueueService(account_name="aarav", account_key="ePdwFBIcH0vLcsYSEdKsslt+d2CpM1YRSDN6ZHtkYh5J9xE06Ebj5pSXFhcV15QkG2xm8EXVsxQwo3NxFh9hLA==")
block_blob_service = BlockBlobService(account_name='aarav', account_key='ePdwFBIcH0vLcsYSEdKsslt+d2CpM1YRSDN6ZHtkYh5J9xE06Ebj5pSXFhcV15QkG2xm8EXVsxQwo3NxFh9hLA==')
app = Flask(__name__)

# J,J_content,J_style,a_C,a_G,out,train_step,optimizer = None
tf.reset_default_graph()
sess = tf.InteractiveSession()
train_step = None
J = None
J_content = None
J_style = None
STYLE_LAYERS = [
    ('conv1_1', 0.2),
    ('conv2_1', 0.2),
    ('conv3_1', 0.2),
    ('conv4_1', 0.2),
    ('conv5_1', 0.2)]

@app.route('/isAlive', methods=['POST', 'GET'])
def index():
    return "true"

def compute_content_cost(a_C, a_G):
    """
    Computes the content cost
    
    Arguments:
    a_C -- tensor of dimension (1, n_H, n_W, n_C), hidden layer activations representing content of the image C 
    a_G -- tensor of dimension (1, n_H, n_W, n_C), hidden layer activations representing content of the image G
    
    Returns: 
    J_content -- scalar that you compute using equation 1 above.
    """
    
    ### START CODE HERE ###
    # Retrieve dimensions from a_G (≈1 line)
    m, n_H, n_W, n_C = a_G.get_shape().as_list()
    
    # Reshape a_C and a_G (≈2 lines)
    a_C_unrolled = tf.transpose(tf.reshape(a_C, [-1]))
    a_G_unrolled = tf.transpose(tf.reshape(a_G, [-1]))
    
    # compute the cost with tensorflow (≈1 line)
    J_content = tf.reduce_sum((a_C_unrolled - a_G_unrolled)**2) / (4 * n_H * n_W * n_C)
    ### END CODE HERE ###
    
    return J_content

def gram_matrix(A):
    """
    Argument:
    A -- matrix of shape (n_C, n_H*n_W)
    
    Returns:
    GA -- Gram matrix of A, of shape (n_C, n_C)
    """
    
    ### START CODE HERE ### (≈1 line)
    GA = GA = tf.matmul(A, tf.transpose(A))
    ### END CODE HERE ###
    
    return GA

def compute_layer_style_cost(a_S, a_G):
    """
    Arguments:
    a_S -- tensor of dimension (1, n_H, n_W, n_C), hidden layer activations representing style of the image S 
    a_G -- tensor of dimension (1, n_H, n_W, n_C), hidden layer activations representing style of the image G
    
    Returns: 
    J_style_layer -- tensor representing a scalar value, style cost defined above by equation (2)
    """
    
    ### START CODE HERE ###
    # Retrieve dimensions from a_G (≈1 line)
    m, n_H, n_W, n_C = a_G.get_shape().as_list()
    
    # Reshape the images to have them of shape (n_H*n_W, n_C) (≈2 lines)
    a_S = tf.reshape(a_S, [n_H*n_W, n_C])
    a_G = tf.reshape(a_G, [n_H*n_W, n_C])

    # Computing gram_matrices for both images S and G (≈2 lines)
    GS = gram_matrix(tf.transpose(a_S)) #notice that the input of gram_matrix is A: matrix of shape (n_C, n_H*n_W)
    GG = gram_matrix(tf.transpose(a_G))

    # Computing the loss (≈1 line)
    J_style_layer = tf.reduce_sum((GS - GG)**2) / (4 * n_C**2 * (n_W * n_H)**2)
    
    ### END CODE HERE ###
    return J_style_layer

def compute_style_cost(model, STYLE_LAYERS):
    """
    Computes the overall style cost from several chosen layers
    
    Arguments:
    model -- our tensorflow model
    STYLE_LAYERS -- A python list containing:
                        - the names of the layers we would like to extract style from
                        - a coefficient for each of them
    
    Returns: 
    J_style -- tensor representing a scalar value, style cost defined above by equation (2)
    """
    
    # initialize the overall style cost
    J_style = 0

    for layer_name, coeff in STYLE_LAYERS:

        # Select the output tensor of the currently selected layer
        out = model[layer_name]

        # Set a_S to be the hidden layer activation from the layer we have selected, by running the session on out
        a_S = sess.run(out)

        # Set a_G to be the hidden layer activation from same layer. Here, a_G references model[layer_name] 
        # and isn't evaluated yet. Later in the code, we'll assign the image G as the model input, so that
        # when we run the session, this will be the activations drawn from the appropriate layer, with G as input.
        a_G = out
        
        # Compute style_cost for the current layer
        J_style_layer = compute_layer_style_cost(a_S, a_G)

        # Add coeff * J_style_layer of this layer to overall style cost
        J_style += coeff * J_style_layer

    return J_style


def total_cost(J_content, J_style, alpha = 10, beta = 40):
    """
    Computes the total cost function
    
    Arguments:
    J_content -- content cost coded above
    J_style -- style cost coded above
    alpha -- hyperparameter weighting the importance of the content cost
    beta -- hyperparameter weighting the importance of the style cost
    
    Returns:
    J -- total cost as defined by the formula above.
    """
    
    ### START CODE HERE ### (≈1 line)
    J = alpha * J_content + beta * J_style
    ### END CODE HERE ###
    
    return J
def model_nn(sess, input_image, num_iterations = 200):
    
    # Initialize global variables (you need to run the session on the initializer)
    ### START CODE HERE ### (1 line)
    sess.run(tf.global_variables_initializer())
    ### END CODE HERE ###
    
    # Run the noisy input image (initial generated image) through the model. Use assign().
    ### START CODE HERE ### (1 line)
    sess.run(model['input'].assign(input_image))
    ### END CODE HERE ###
    
    for i in range(num_iterations):
    
        # Run the session on the train_step to minimize the total cost
        ### START CODE HERE ### (1 line)
        _ = sess.run(train_step)
        ### END CODE HERE ###
        
        # Compute the generated image by running the session on the current model['input']
        ### START CODE HERE ### (1 line)
        generated_image = sess.run(model['input'])# (1 line)
        ### END CODE HERE ###

        # Print every 20 iteration.
        if i%20 == 0:
            Jt, Jc, Js = sess.run([J, J_content, J_style])
            print("Iteration " + str(i) + " :")
            print("total cost = " + str(Jt))
            print("content cost = " + str(Jc))
            print("style cost = " + str(Js))
            
            # save current generated image in the "/output" directory
            save_image("output/" + str(i) + ".png", generated_image)
    
    # save last generated image
    save_image('output/generated_image.jpg', generated_image)
    
    return generated_image

def transfer(path1,path2):
    # Reset the graph
    global sess
    global model
    # global out
    global train_step
    # global a_C
    # global a_G
    global J
    global J_content
    global J_style
    # global optimizer
    content_image = scipy.misc.imread(path1)
    content_image = reshape_and_normalize_image(content_image)

    style_image = scipy.misc.imread(path2)
    style_image = reshape_and_normalize_image(style_image)

    generated_image = generate_noise_image(content_image)
    imshow(generated_image[0])
    tf.reset_default_graph()
    sess = tf.InteractiveSession()
    model = load_vgg_model("pretrained-model/imagenet-vgg-verydeep-19.mat")

    # Assign the content image to be the input of the VGG model.  
    sess.run(model['input'].assign(content_image))

    # Select the output tensor of layer conv4_2
    out = model['conv4_2']

    # Set a_C to be the hidden layer activation from the layer we have selected
    a_C = sess.run(out)

    # Set a_G to be the hidden layer activation from same layer. Here, a_G references model['conv4_2'] 
    # and isn't evaluated yet. Later in the code, we'll assign the image G as the model input, so that
    # when we run the session, this will be the activations drawn from the appropriate layer, with G as input.
    a_G = out

    # Compute the content cost
    J_content = compute_content_cost(a_C, a_G)

    # Assign the input of the model to be the "style" image 
    sess.run(model['input'].assign(style_image))

    # Compute the style cost
    J_style = compute_style_cost(model, STYLE_LAYERS)

    ### START CODE HERE ### (1 line)
    J = total_cost(J_content, J_style,  alpha = 10, beta = 40)
    ### END CODE HERE ###

    # define optimizer (1 line)
    optimizer = tf.train.AdamOptimizer(2.0)

    # define train_step (1 line)
    train_step = optimizer.minimize(J)



    model_nn(sess, generated_image)


def checkQueue(checkQueue_on):
    ctr = 0
    while True:
        # queue_service.put_message("jsonqueue","hello world")
        messages = queue_service.get_messages('jsonqueue', num_messages=1, visibility_timeout=5*60)
        ctr = ctr + 1
        if(ctr == 100):
            ctr = 0
            print(True)
        d = {}
        for message in messages:
            d = json.loads(QueueMessageFormat.text_base64decode(message.content))
            print(d["uri1"])
            print(d["uri2"])
            urllib.request.urlretrieve(d["uri1"], "1.jpg")
            urllib.request.urlretrieve(d["uri2"], "2.jpg")
            transfer("1.jpg","2.jpg")
            block_blob_service.create_blob_from_path("detectedimages",d["guid"], "output/generated_image.jpg")
            queue_service.delete_message("jsonqueue",message.id,message.pop_receipt) 

if __name__ == '__main__':
    checkQueue_on = Value('b', True)
    p = Process(target=checkQueue, args=(checkQueue_on,))
    p.start()
    app.run(host='0.0.0.0', use_reloader=False)
    p.join()