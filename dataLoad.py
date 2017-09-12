import numpy as np
import shutil, time, math, itertools, os
import h5py
#import netCDF4 as nc 
#from netCDF4 import Dataset
from tqdm import tqdm
import tensorflow as tf
import threading
import random
from colorama import Fore, Back, Style
import sys
from folderDefs import *

class DataLoader:
    def __init__(self, folderPath, config):
        self.config = config
        self.batchSize = config.batch_size
        self.nSampleFetching = 1024
        self.varname = config.dataset
        self.fileReader = []
        self.lock = threading.Lock()
        self.inputNames = ['QAP', 'TAP', 'OMEGA', 'GRAD_UQ_H', 'SHFLX', 'LHFLX']
        self.reload()

    def reload(self, finishedEpoch = 0):
        # need to retrieve mean and standard deviation of the full dataset first
        print("Reading Netcdfs mean and std for Normalization")
        self.mean = {}
        self.std = {}
        self.max = {}
        with h5py.File(nc_mean_file, mode='r') as fh:
            for k in fh.keys():
                try:
                    self.mean[k] = fh[k][None,:]
                except:
                    self.mean[k] = np.array(fh[k])[None]
                print('nc_mean_file: ', k, self.mean[k].shape)#, self.mean[k])
        with h5py.File(nc_std_file, mode='r') as fh:
            for k in fh.keys():
                try:
                    self.std[k] = fh[k][None,:]
                except:
                    self.std[k] = np.array(fh[k])[None]
                print('nc_std_file: ', k, self.std[k].shape)#, self.std[k])
 
        with h5py.File(nc_max_file, mode='r') as fh: # normalize outputs to be between -1 and 1
            for k in fh.keys():
                try:
                    self.max[k] = fh[k][None,:]
                except:
                    self.max[k] = np.array(fh[k])[None]
                print('nc_max_file: ', k, self.max[k].shape)#, self.max[k])
        
        print("End Reading Netcdfs for Normalization")
        try:
            for i in range(len(self.fileReader)):
                self.fileReader[i].close()
        except:
            pass
        print("batchSize = ", self.batchSize)

        with h5py.File(nc_file, mode='r') as fh:
            for k in fh.keys():
                print('nc_file: ', k, fh[k].shape)
            self.Nsamples = fh['PS'].shape[0]
            print('Nsamples =', self.Nsamples)
            self.Nlevels      = self.mean['QAP'].shape[1]
            print('Nlevels = ', self.Nlevels)
            sampX, sampY = self.accessData(0, self.nSampleFetching, fh)
            self.n_input = 4*self.Nlevels + 2  # number of levels plus three surface data (PS, SHFLX, LHFLX)
            self.n_output = fh[self.varname][:].shape[0] # remove first 9 indices
            print('n_input = ', self.n_input)
            print('n_output = ', self.n_output)

        self.NumBatch = self.Nsamples // self.config.batch_size
        self.NumBatchTrain = int(self.Nsamples * self.config.frac_train) // self.batchSize
        self.indexValidation = self.NumBatchTrain * self.batchSize
        self.NumBatchValid = int(self.Nsamples * (1.0 - self.config.frac_train)) // self.config.batch_size
        print('NumBatch=', self.NumBatch)
        print('NumBatchTrain=', self.NumBatchTrain)
        print('indexValidation=', self.indexValidation)
        print('NumBatchValid=', self.NumBatchValid)

        self.samplesTrain = range(0, self.indexValidation, self.nSampleFetching)
        self.randSamplesTrain = list(self.samplesTrain)
        if self.config.randomize:
            random.shuffle(self.randSamplesTrain)
        self.samplesValid = range(self.indexValidation, self.Nsamples, self.nSampleFetching)
        self.randSamplesValid = list(self.samplesValid)
        if self.config.randomize:
            random.shuffle(self.randSamplesValid)
        self.numFetchesTrain = len(self.randSamplesTrain)
        self.numFetchesValid = len(self.randSamplesValid)
        print('randSamplesTrain', self.randSamplesTrain[:16], self.numFetchesTrain)
        print('randSamplesValid', self.randSamplesValid[:16], self.numFetchesValid)
        self.posTrain = 0
        self.posValid = 0

        self.Xshape = list(sampX.shape[1:])
        self.Yshape = list(sampY.shape[1:])
        print('Xshape', self.Xshape)
        print('Yshape', self.Yshape)

    def __enter__(self):
        return self
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            for i in range(len(self.fileReader)):
                self.fileReader[i].close()
        except:
            pass

    def accessData(self, s, l, fileReader):
        self.inputs = []
        for k in self.inputNames:#fileReader.keys():
            #print('nc_file: ', k, fileReader[k].shape)
            try:
                arr = fileReader[k][:,s:s+l].T
            except:
                arr = np.array(fileReader[k][s:s+l])[None,:].T

        #QAP      = fh['QAP'][:,s:s+l]       # QAP    kg/kg   30   Specific humidity (after physics)
        #TAP      = fh['TAP'][:,s:s+l]       # TAP    K       30   Temperature (after physics)
        #OMEGA    = fh['OMEGA'][:,s:s+l]     # OMEGA  Pa/s    30   Vertical velocity (pressure)
        #UBSP     = fh['UBSP'][:,s:s+l]      # UBSP  m/s   30   Meridional wind
        #VBSP     = fh['VBSP'][:,s:s+l]      # VBSP  m/s   30   Meridional wind
        #dTdt_adiabatic     = fh['dTdt_adiabatic'][:,s:s+l]      # Adiabatic T tendencies  K/s  30
        #dQdt_adiabatic     = fh['dQdt_adiabatic'][:,s:s+l]      # Adiabatic q tendencies  kg/kg/s  30
        #GRAD_UQ_H= fh['GRAD_UQ_H'][:,s:s+l]      # Adiabatic q tendencies  kg/kg/s  30
        #QRS      = fh['QRS'][:,s:s+l]      # Adiabatic q tendencies  kg/kg/s  30
        #QRL      = fh['QRL'][:,s:s+l]      # Adiabatic q tendencies  kg/kg/s  30
        #PS       = fh['PS'][s:s+l][None]    # PS     Pa      1    Surface pressure
        #SHFLX    = fh['SHFLX'][s:s+l][None] # SHFLX  W/m2    1    Surface sensible heat flux
        #LHFLX    = fh['LHFLX'][s:s+l][None] # LHFLX  W/m2    1    Surface latent heat flux

            # normalize data
            if self.config.normalize:
                arr -= self.mean[k]
                arr /= self.std[k]
            if s == 0:
                print('nc_file: ', k, arr.shape)

        #QAP      = (QAP - self.mean_QAP) / self.std_QAP
        #TAP      = (TAP - self.mean_TAP) / self.std_TAP
        #OMEGA    = (OMEGA - self.mean_OMEGA) / self.std_OMEGA
        #UBSP     = (UBSP - self.mean_UBSP) / self.std_UBSP
        #VBSP     = (VBSP - self.mean_VBSP) / self.std_VBSP
        #dTdt_adiabatic     = (dTdt_adiabatic - self.mean_dTdt_adiabatic) / self.std_dTdt_adiabatic
        #dQdt_adiabatic     = (dQdt_adiabatic - self.mean_dQdt_adiabatic) / self.std_dQdt_adiabatic
        #QRS     = (QRS - self.mean_QRS) / self.std_QRS
        #QRL     = (QRL - self.mean_QRL) / self.std_QRL
        #GRAD_UQ_H     = (GRAD_UQ_H - self.mean_GRAD_UQ_H) / self.std_GRAD_UQ_H
        #PS       = (PS - self.mean_PS) / self.std_PS
        #SHFLX    = (SHFLX - self.mean_SHFLX) / self.std_SHFLX
        #LHFLX    = (LHFLX - self.mean_LHFLX) / self.std_LHFLX
            if arr.shape[-1] == 1:
                arr = np.tile(arr, (1,self.Nlevels))
                #print('nc_file: ', k, arr.shape)
            self.inputs += [arr]
        # input data
        inX = np.stack(self.inputs, axis=1)

        # output data
        y_data   = fileReader[self.varname][:,s:s+l].T      # SPDT   K/s     30   dT/dt

        if s == 0:
            print('y_data.shape', y_data.shape)
            print('inX.shape', inX.shape)

        #y_data *= 1.e10 # jsut to increase magnitude of SPDT and SPDQ for better convergence

        return inX, y_data

    def sampleTrain(self, ithFileReader):
#        self.lock.acquire()
        s = self.randSamplesTrain[self.posTrain]
        #print(ithFileReader, self.posTrain, s)
        self.posTrain += 1
        self.posTrain %= self.numFetchesTrain
#        self.lock.release()
        x,y = self.accessData(s, self.nSampleFetching, self.fileReader[ithFileReader])
        return x,y

    def sampleValid(self, ithFileReader):
        s = self.randSamplesValid[self.posValid]
        self.posValid += 1
        self.posValid %= self.numFetchesValid
        x,y = self.accessData(s, self.nSampleFetching, self.fileReader[ithFileReader])
        return x,y

    def data_iterator(self, ithFileReader):
        """ A simple data iterator """
        print('data_iterator', ithFileReader, threading.current_thread())
        while True:
            sampX, sampY = self.sampleTrain(ithFileReader) if self.config.is_train else self.sampleValid(ithFileReader)
            yield sampX, sampY

    def prepareQueue(self):
        with tf.name_scope('prepareQueue'):
            self.dataX = tf.placeholder(dtype=tf.float32, shape=[None]+self.Xshape)
            self.dataY = tf.placeholder(dtype=tf.float32, shape=[None]+self.Yshape)

            self.capacityTrain = max(self.nSampleFetching * 32, self.batchSize * 8) if self.config.is_train else self.batchSize
            if self.config.randomize:
                self.queue = tf.RandomShuffleQueue(shapes=[self.Xshape, self.Yshape],
                                               dtypes=[tf.float32, tf.float32],
                                               capacity=self.capacityTrain,
                                               min_after_dequeue=self.capacityTrain // 2
                                               )
            else:
                self.queue = tf.FIFOQueue(shapes=[self.Xshape, self.Yshape],
                                               dtypes=[tf.float32, tf.float32],
                                               capacity=self.capacityTrain
                                               )
            self.enqueue_op = self.queue.enqueue_many([self.dataX, self.dataY])
            self.size_op = self.queue.size()

    def get_inputs(self):
        with tf.name_scope('dequeue'):
            train0Valid1 = tf.placeholder_with_default(1, [], name='train0Valid1')
            b_X, b_Y = self.queue.dequeue_many(self.batchSize)
            print("b_X",b_X.get_shape(), "b_Y",b_Y.get_shape())
            return b_X, b_Y

    def thread_main(self, sess, ithFileReader):
        print('thread_main', ithFileReader, threading.current_thread())
        while len(self.fileReader) <= ithFileReader + 1:
            self.fileReader += [h5py.File(nc_file, mode='r')]
        for dtX, dtY in self.data_iterator(ithFileReader):
            sess.run(self.enqueue_op, feed_dict={self.dataX:dtX, self.dataY:dtY})

    def start_threads(self, sess, n_threads=4):
        """ Start background threads to feed queue """
        threads = []
        print("starting %d data threads for training" % n_threads)
        for n in range(n_threads):
            t = threading.Thread(target=self.thread_main, args=(sess,0,))
            t.daemon = True # thread will close when parent quits
            t.start()
            threads.append(t)
        # Make sure the queueu is filled with some examples (n = 500)
        num_samples_in_queue = 0
        while num_samples_in_queue < self.capacityTrain:
            num_samples_in_queue = sess.run(self.size_op)
            print("Initializing queue, current size = %i/%i" % (num_samples_in_queue, self.capacityTrain))
            time.sleep(2)
        return threads

