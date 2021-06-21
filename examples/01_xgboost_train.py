import xgboost as xgb 
import pandas as pd
import numpy as np

import re
import urllib.request
from konlpy.tag import Okt
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences

from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix, accuracy_score, precision_score, recall_score
from sklearn.metrics import confusion_matrix, f1_score, roc_auc_score
import warnings
from xgboost import XGBClassifier
import pickle
import os

def get_vocab_size():
    tokenizer = Tokenizer()
    tokenizer.fit_on_texts(X_train)
    threshold = 3
    total_cnt = len(tokenizer.word_index) # 단어의 수
    rare_cnt = 0 # 등장 빈도수가 threshold보다 작은 단어의 개수를 카운트
    total_freq = 0 # 훈련 데이터의 전체 단어 빈도수 총 합
    rare_freq = 0 # 등장 빈도수가 threshold보다 작은 단어의 등장 빈도수의 총 합

    # 단어와 빈도수의 쌍(pair)을 key와 value로 받는다.
    for key, value in tokenizer.word_counts.items():
        total_freq = total_freq + value

        # 단어의 등장 빈도수가 threshold보다 작으면
        if(value < threshold):
            rare_cnt = rare_cnt + 1
            rare_freq = rare_freq + value

    # 전체 단어 개수 중 빈도수 2이하인 단어는 제거.
    # 0번 패딩 토큰을 고려하여 + 1
    vocab_size = total_cnt - rare_cnt + 1
    return vocab_size

# dump to pickle
def write2file(data, filepath):
    with open(filepath, 'wb') as f:
        pickle.dump(data, f)

def preprocess():
    train_data = pd.read_table('ratings_train.txt')
    test_data = pd.read_table('ratings_test.txt')
    
    train_data.drop_duplicates(subset=['document'], inplace=True) # document 열에서 중복인 내용이 있다면 중복 제거
    
    train_data = train_data.dropna(how = 'any') # Null 값이 존재하는 행 제거
    
    train_data['document'] = train_data['document'].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 ]","")
    # 한글과 공백을 제외하고 모두 제거
    
    train_data['document'] = train_data['document'].str.replace('^ +', "") # white space 데이터를 empty value로 변경
    train_data['document'].replace('', np.nan, inplace=True)
    
    train_data = train_data.dropna(how = 'any')
    
    test_data.drop_duplicates(subset = ['document'], inplace=True) # document 열에서 중복인 내용이 있다면 중복 제거
    test_data['document'] = test_data['document'].str.replace("[^ㄱ-ㅎㅏ-ㅣ가-힣 ]","") # 정규 표현식 수행
    test_data['document'] = test_data['document'].str.replace('^ +', "") # 공백은 empty 값으로 변경
    test_data['document'].replace('', np.nan, inplace=True) # 공백은 Null 값으로 변경
    test_data = test_data.dropna(how='any') # Null 값 제거
    
    stopwords = ['의','가','이','은','들','는','좀','잘','걍','과','도','를','으로','자','에','와','한','하다']
    
    okt = Okt()
    
    X_train = []
    total_len = len(train_data['document'])
    cnt = 0
    print('train_data : stopwords eliminating ==========')
    for sentence in train_data['document']:
        temp_X = okt.morphs(sentence, stem=True) # 토큰화
        temp_X = [word for word in temp_X if not word in stopwords] # 불용어 제거
        X_train.append(temp_X)
        cnt += 1
        if(cnt % 1000 == 0):
            print('(%d / %d) processing...' % (cnt, total_len))
    
    X_test = []
    total_len = len(test_data['document'])
    cnt = 0
    print('test_data : stopwords eliminating ==========')
    for sentence in test_data['document']:
        temp_X = okt.morphs(sentence, stem=True) # 토큰화
        temp_X = [word for word in temp_X if not word in stopwords] # 불용어 제거
        X_test.append(temp_X)
        cnt += 1
        if(cnt % 1000 == 0):
            print('(%d / %d) processing...' % (cnt, total_len))
    
    vocab_size = get_vocab_size()
    
    tokenizer = Tokenizer(vocab_size) 
    tokenizer.fit_on_texts(X_train)
    X_train = tokenizer.texts_to_sequences(X_train)
    X_test = tokenizer.texts_to_sequences(X_test)
    
    y_train = np.array(train_data['label'])
    y_test = np.array(test_data['label'])
    
    drop_train = [index for index, sentence in enumerate(X_train) if len(sentence) < 1]
    
    # 빈 샘플들을 제거
    X_train = np.delete(X_train, drop_train, axis=0)
    y_train = np.delete(y_train, drop_train, axis=0)
    
    max_len = 30
    X_train = pad_sequences(X_train, maxlen = max_len)
    X_test = pad_sequences(X_test, maxlen = max_len)
    
    # dump data to pickle
    write2file(X_train, 'X_train.pkl')
    write2file(X_test, 'X_test.pkl')
    write2file(y_train, 'y_train.pkl')
    write2file(y_test, 'y_test.pkl')

def load2var(filepath):
    with open(filepath, 'rb') as f:
        data = pickle.load(f)
        return data

fname1 = 'X_train.pkl'
fname2 = 'X_test.pkl'
if(os.path.isfile(fname1) and os.path.isfile(fname2)):
    print('load data from pickle')
    
    # load to data variable
    X_train = load2var('X_train.pkl')
    X_test = load2var('X_test.pkl')
    y_train = load2var('y_train.pkl')
    y_test = load2var('y_test.pkl')
else:
    # 데이터 사전처리
    preprocess()

# max_depth = 3, 학습률은 0.1, 예제가 이진분류이므로 목적함수(objective)는 binary:logistic(이진 로지스틱)
# 부스팅 반복횟수는 400
xgb_wrapper = XGBClassifier(n_estimators = 400, learning_rate = 0.1 , max_depth = 3)
evals = [(X_test, y_test)]
xgb_wrapper.fit(X_train, y_train, early_stopping_rounds = 100, 
                eval_metric="logloss", eval_set = evals, verbose=True)
w_preds = xgb_wrapper.predict(X_test)

# dump mode data to pickle
write2file(xgb_wrapper, 'best_xgboost_model.pkl')
