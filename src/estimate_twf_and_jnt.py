#! /usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Estimate joint feature vector of the speaker pair using GMM

"""

import argparse
import os
import sys

from sprocket.model.GMM import GMMConvertor, GMMTrainer
from sprocket.util import HDF5, estimate_twf, melcd
from sprocket.util import static_delta, align_data 
from sprocket.util.twf import align_ppg_data
from yml import SpeakerYML, PairYML
from misc import read_feats, extsddata, transform_jnt, read_ppg_feats, exts_post_data, exts_post_FA
import numpy as np

def get_alignment(odata, onpow, tdata, tnpow, opow=-20, tpow=-20,
                  sd=0, cvdata=None, given_twf=None, otflag=None,
                  distance='melcd'):
    """Get alignment between original and target

    Paramters
    ---------
    odata : array, shape (`T`, `dim`)
        Acoustic feature vector of original
    onpow : array, shape (`T`)
        Normalized power vector of original
    tdata : array, shape (`T`, `dim`)
        Acoustic feature vector of target
    tnpow : array, shape (`T`)
        Normalized power vector of target
    opow : float, optional,
        Power threshold of original
        Default set to -20
    tpow : float, optional,
        Power threshold of target
        Default set to -20
    sd : int , optional,
        Start dimension to be used for alignment
        Default set to 0
    cvdata : array, shape (`T`, `dim`), optional,
        Converted original data
        Default set to None
    given_twf : array, shape (`T_new`, `dim * 2`), optional,
        Alignment given twf
        Default set to None
    otflag : str, optional
        Alignment into the length of specification
        'org' : alignment into original length
        'tar' : alignment into target length
        Default set to None
    distance : str,
        Distance function to be used
        Default set to 'melcd'

    Returns
    -------
    jdata : array, shape (`T_new` `dim * 2`)
        Joint static and delta feature vector
    twf : array, shape (`T_new` `dim * 2`)
        Time warping function
    mcd : float,
        Mel-cepstrum distortion between arrays

    """

    oexdata = extsddata(odata[:, sd:], onpow,
                        power_threshold=opow)
    texdata = extsddata(tdata[:, sd:], tnpow,
                        power_threshold=tpow)

    if cvdata is None:
        align_odata = oexdata
    else:
        cvexdata = extsddata(cvdata, onpow,
                             power_threshold=opow)
        align_odata = cvexdata

    if given_twf is None:
        twf = estimate_twf(align_odata, texdata,
                           distance=distance, otflag=otflag)
    else:
        twf = given_twf

    jdata = align_data(oexdata, texdata, twf)
    mcd = melcd(align_odata[twf[0]], texdata[twf[1]])
    print("Done get alignment")
    return jdata, twf, mcd

def get_ppg_alignment(odata, onpow, tdata, tnpow, s_name,t_name,
                opow=-20, tpow=-20,
                  sd=0,cvdata=None, given_twf=None, otflag=None,
                  distance='melcd'):
    
    # oexdata = extsddata(odata[:, sd:], onpow,
    #                     power_threshold=opow)
    # texdata = extsddata(tdata[:, sd:], tnpow,
    #                     power_threshold=tpow)
    s_post_name = "post." + s_name[-12:] + ".ark"
    t_post_name = "post." + t_name[-12:] + ".ark"
    s_post = os.path.join("/home/anurag/kaldi/egs/librispeech/s5/post_source/",s_post_name)
    t_post = os.path.join("/home/anurag/kaldi/egs/librispeech/s5/post_target/",t_post_name)
    s_FA = os.path.join("/home/anurag/Downloads/l2arctic_release/BDL_0.99/FA/",s_name[-12:] + ".txt")
    t_FA = os.path.join("/home/anurag/Downloads/l2arctic_release/ABA_16k/FA/",t_name[-12:] + ".txt")
    s_post = exts_post_FA(np.loadtxt(s_post),s_FA)
    t_post = exts_post_FA(np.loadtxt(t_post),t_FA)
    #s_post = exts_post_data(np.loadtxt(s_post),onpow,power_threshold=opow)
    #t_post = exts_post_data(np.loadtxt(t_post),tnpow,power_threshold=tpow)
    oexdata = exts_post_FA(odata[:, sd:],s_FA,delta=True)
    texdata = exts_post_FA(tdata[:, sd:],t_FA,delta=True)
    if cvdata is None:
        align_odata = oexdata
    else:
        cvexdata = extsddata(cvdata, onpow,
                             power_threshold=opow)
        align_odata = cvexdata

    # if given_twf is None:
    #     twf = estimate_twf(align_odata, texdata,
    #                        distance=distance, otflag=otflag)
    # else:
    #     twf = given_twf

    #jdata = align_data(oexdata, texdata, twf)
    jdata = align_ppg_data(oexdata,texdata,s_post,t_post)
    # mcd = melcd(align_odata[twf[0]], texdata[twf[1]])
    print("Done get alignment")
    return jdata


def align_feature_vectors(odata, onpows, tdata, tnpows, pconf,
                          opow=-100, tpow=-100, itnum=3, sd=0,
                          given_twfs=None, otflag=None):
    """Get alignment to create joint feature vector

    Paramters
    ---------
    odata : list, (`num_files`)
        List of original feature vectors
    onpows : list , (`num_files`)
        List of original npows
    tdata : list, (`num_files`)
        List of target feature vectors
    tnpows : list , (`num_files`)
        List of target npows
    opow : float, optional,
        Power threshold of original
        Default set to -100
    tpow : float, optional,
        Power threshold of target
        Default set to -100
    itnum : int , optional,
        The number of iteration
        Default set to 3
    sd : int , optional,
        Start dimension of feature vector to be used for alignment
        Default set to 0
    given_twf : array, shape (`T_new` `dim * 2`)
        Use given alignment while 1st iteration
        Default set to None
    otflag : str, optional
        Alignment into the length of specification
        'org' : alignment into original length
        'tar' : alignment into target length
        Default set to None

    Returns
    -------
    jfvs : list,
        List of joint feature vectors
    twfs : list,
        List of time warping functions
    """
    num_files = len(odata)
    cvgmm, cvdata = None, None
    for it in range(1, itnum + 1):
        print('{}-th joint feature extraction starts.'.format(it))
        twfs, jfvs = [], []
        for i in range(num_files):
            if it == 1 and given_twfs is not None:
                gtwf = given_twfs[i]
            else:
                gtwf = None
            if it > 1:
                cvdata = cvgmm.convert(static_delta(odata[i][:, sd:]),
                                       cvtype=pconf.GMM_mcep_cvtype)
            jdata, twf, mcd = get_alignment(odata[i],
                                            onpows[i],
                                            tdata[i],
                                            tnpows[i],
                                            opow=opow,
                                            tpow=tpow,
                                            sd=sd,
                                            cvdata=cvdata,
                                            given_twf=gtwf,
                                            otflag=otflag)
            twfs.append(twf)
            jfvs.append(jdata)
            print('distortion [dB] for {}-th file: {}'.format(i + 1, mcd))
        jnt_data = transform_jnt(jfvs)

        if it != itnum:
            # train GMM, if not final iteration
            print("training GMM")
            datagmm = GMMTrainer(n_mix=pconf.GMM_mcep_n_mix,
                                 n_iter=pconf.GMM_mcep_n_iter,
                                 covtype=pconf.GMM_mcep_covtype)
            datagmm.train(jnt_data)
            cvgmm = GMMConvertor(n_mix=pconf.GMM_mcep_n_mix,
                                 covtype=pconf.GMM_mcep_covtype)
            cvgmm.open_from_param(datagmm.param)
        it += 1
    return jfvs, twfs

def align_ppg_feature_vectors(odata, onpows, tdata, tnpows, pconf,
                          s_list_file,tar_list_file,
                          opow=-100, tpow=-100, itnum=3, sd=0,
                          given_twfs=None, otflag=None):
    s_list_file = np.loadtxt(s_list_file,dtype='str')
    tar_list_file = np.loadtxt(tar_list_file,dtype='str')
    num_files = len(odata)
    cvgmm, cvdata = None, None
    jfvs = [] 
    for it in range(1, itnum + 1):
        print('{}-th joint feature extraction starts.'.format(it))
        twfs = []
        for i in range(num_files):
            if it == 1 and given_twfs is not None:
                gtwf = given_twfs[i]
            else:
                gtwf = None
            if it > 1:
                cvdata = cvgmm.convert(static_delta(odata[i][:, sd:]),
                                       cvtype=pconf.GMM_mcep_cvtype)
            if it == 1:
                jdata = get_ppg_alignment(odata[i],
                                                onpows[i],
                                                tdata[i],
                                                tnpows[i],
                                                s_list_file[i],
                                                tar_list_file[i],
                                                opow=opow,
                                                tpow=tpow,
                                                sd=sd,                                    
                                                cvdata=cvdata,
                                                given_twf=gtwf,
                                                otflag=otflag)
                print(s_list_file[i])
                jfvs.append(jdata)
                jnt_data = transform_jnt(jfvs)
            _ , twf, _ = get_alignment(odata[i],
                                            onpows[i],
                                            tdata[i],
                                            tnpows[i],
                                            opow=opow,
                                            tpow=tpow,
                                            sd=sd,
                                            cvdata=cvdata,
                                            given_twf=gtwf,
                                            otflag=otflag)  
            twfs.append(twf)

        if it != itnum:
            # train GMM, if not final iteration
            print("training GMM")
            datagmm = GMMTrainer(n_mix=pconf.GMM_mcep_n_mix,
                                 n_iter=pconf.GMM_mcep_n_iter,
                                 covtype=pconf.GMM_mcep_covtype)
            datagmm.train(jnt_data)
            cvgmm = GMMConvertor(n_mix=pconf.GMM_mcep_n_mix,
                                 covtype=pconf.GMM_mcep_covtype)
            cvgmm.open_from_param(datagmm.param)
        it += 1
    return jfvs, twfs


def main(*argv):
    argv = argv if argv else sys.argv[1:]
    # Options for python
    description = 'estimate joint feature of source and target speakers'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('org_yml', type=str,
                        help='Yml file of the original speaker')
    parser.add_argument('tar_yml', type=str,
                        help='Yml file of the target speaker')
    parser.add_argument('pair_yml', type=str,
                        help='Yml file of the speaker pair')
    parser.add_argument('org_list_file', type=str,
                        help='List file of original speaker')
    parser.add_argument('tar_list_file', type=str,
                        help='List file of target speaker')
    parser.add_argument('pair_dir', type=str,
                        help='Directory path of h5 files')
    args = parser.parse_args(argv)

    # read speaker-dependent yml files
    oconf = SpeakerYML(args.org_yml)
    tconf = SpeakerYML(args.tar_yml)

    # read pair-dependent yml file
    pconf = PairYML(args.pair_yml)

    # read source and target features from HDF file
    h5_dir = os.path.join(args.pair_dir, 'h5')
    # org_mceps, tar_mceps = read_ppg_feats(args.org_list_file, args.tar_list_file, h5_dir, ext='mcep')
    org_mceps = read_feats(args.org_list_file, h5_dir, ext='mcep')
    org_npows = read_feats(args.org_list_file, h5_dir, ext='npow')
    tar_mceps = read_feats(args.tar_list_file, h5_dir, ext='mcep')
    tar_npows = read_feats(args.tar_list_file, h5_dir, ext='npow')
    assert len(org_mceps) == len(tar_mceps)
    assert len(org_npows) == len(tar_npows)
    assert len(org_mceps) == len(org_npows)

    # dtw between original and target w/o 0th and silence
    print('## Alignment mcep w/o 0-th and silence ##')
    jmceps, twfs = align_ppg_feature_vectors(org_mceps,
                                         org_npows,
                                         tar_mceps,
                                         tar_npows,
                                         pconf,
                                         args.org_list_file,
                                         args.tar_list_file,
                                         opow=oconf.power_threshold,
                                         tpow=tconf.power_threshold,
                                         itnum=pconf.jnt_n_iter,
                                         sd=1,
                                         )
    # jmceps, twfs = align_feature_vectors(org_mceps,
    #                                      org_npows,
    #                                      tar_mceps,
    #                                      tar_npows,
    #                                      pconf,
    #                                      opow=oconf.power_threshold,
    #                                      tpow=tconf.power_threshold,
    #                                      itnum=pconf.jnt_n_iter,
    #                                      sd=1,
    #                                      )
    jnt_mcep = transform_jnt(jmceps)

    # # create joint featurehome/anurag/kaldi/egs/librispeech/s5/post_source/post.arctic_a0005.ark for codeap using given twfs
    print('## Alignment codeap using given twf ##')
    org_codeaps = read_feats(args.org_list_file, h5_dir, ext='codeap')
    tar_codeaps = read_feats(args.tar_list_file, h5_dir, ext='codeap')
    jcodeaps = []
    for i in range(len(org_codeaps)):
        # extract codeap joint feature vector
        jcodeap, _, _ = get_alignment(org_codeaps[i],
                                      org_npows[i],
                                      tar_codeaps[i],
                                      tar_npows[i],
                                      opow=oconf.power_threshold,
                                      tpow=tconf.power_threshold,
                                      given_twf=twfs[i])
        jcodeaps.append(jcodeap)
    jnt_codeap = transform_jnt(jcodeaps)

    # # save joint feature vectors
    jnt_dir = os.path.join(args.pair_dir, 'jnt')
    os.makedirs(jnt_dir, exist_ok=True)
    jntpath = os.path.join(jnt_dir, 'it' + str(pconf.jnt_n_iter) + '_jnt.h5')
    jnth5 = HDF5(jntpath, mode='a')
    jnth5.save(jnt_mcep, ext='mcep')
    jnth5.save(jnt_codeap, ext='codeap')
    jnth5.close()

    # # save twfs
    twf_dir = os.path.join(args.pair_dir, 'twf')
    os.makedirs(twf_dir, exist_ok=True)
    with open(args.org_list_file, 'r') as fp:
        for line, twf in zip(fp, twfs):
            f = os.path.basename(line.rstrip())
            twfpath = os.path.join(
                twf_dir, 'it' + str(pconf.jnt_n_iter) + '_' + f + '.h5')
            twfh5 = HDF5(twfpath, mode='a')
            twfh5.save(twf, ext='twf')
            twfh5.close()


if __name__ == '__main__':
    main()
