'''
指令:基础ai;文本推理,你是谁

'''


#文本推理
def basicai_text_reasoning(*parameters):
    parameters = [*parameters]
    prompt = parameters[0]
    rst = aggregation_chat(prompt)
    return rst

#服务调用文本推理
def reference_by_text_reasoning(*parameters):
    parameters = [*parameters]
    print(parameters)
    if len(parameters) == 1:
        prompt_obj = parameters[0]
        # print(prompt_obj)
        rst = aggregation_messages(prompt_obj)#[0]
        #不清楚多参数的意义了
    elif  len(parameters) == 2:
        if parameters[0] == '%!':
            prompt_obj = json.loads(parameters[1].replace('%','{').replace('!',','))
            print(prompt_obj)
            print('111')
            rst = aggregation_messages(prompt_obj)#[0]
        elif  parameters[0] == 'rule':
            if type(parameters[1]) ==type('s'):
                prompt_obj = json.loads(parameters[1])
            else:
                prompt_obj =parameters[1]
            print(prompt_obj)
            print('222')
            rst = aggregation_messages(prompt_obj)#[0]
        else:
            rst = '参数错误'
    else:
        rst = '参数错误'
    return rst

#select_free_inferencemoda
def basicai_text_free_inferencemoda(*parameters):
    parameters = [*parameters]
    prompt = parameters[0]
    rst = select_free_inferencemoda(prompt)
    return rst


#图像推理
def basicai_picture_reasoning(*parameters):
    parameters = [*parameters]
    image_path = parameters[1]
    prompt = parameters[0]
    rst = aggregation_VL(image_path,prompt)
    return rst

#####################################

modelscope_url = 'https://api-inference.modelscope.cn/v1'
xinghuo_url = 'https://spark-api-open.xf-yun.com/v1/chat/completions'
zp_url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'

xinghuo_key = 'Bearer '+get_power_by_name('xunfei')
zp_key = 'Bearer '+get_power_by_name('zhipu')
tongyi_key = get_power_by_name('tongyi')
modelscope_key = get_power_by_name('modelscope')



def aggregation_messages(role):
    u_messages=role
    rst = select_inferencemoda(u_messages)
    return rst


def aggregation_chat(role):
	if type(role) == type([]):
		u_messages=role
	else:
		u_messages=[{'role': 'user','type':'text','content': role}]
	rst = select_inferencemoda(u_messages)
	return rst

def aggregation_VL(image_path,prompt):
    if 'http' in image_path:
        pass
    else:
        image_path = image_to_base64(image_path)
    u_messages=[
    {
      "role": "user",
      "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": image_path}}
      ]
    }
  ]
    rst = select_inferencemoda_v(u_messages)
    return rst


#########################################


def get_beijing_time_period():
    beijing_tz = timezone(timedelta(hours=8))
    now = datetime.now(beijing_tz)
    current_hour = now.hour
    if 0 <= current_hour < 6:
        return 1
    elif 6 <= current_hour < 18:
        return 2
    else:  # 18 <= current_hour < 24
        return 3




####################

def inferencemodel(massage, model_name,url,key):
	client = OpenAI(base_url=url,api_key=key)
	response = client.chat.completions.create(model=model_name,messages=massage,stream=False)
	if response.choices == None:
		rst_data= '当前模型不可用'
	else:
		rst_data = response.choices[0].message.content
	return rst_data



def free_llm_modle(massage, model_name,modle_url,modle_key):
	headers = {"Content-Type": "application/json","Authorization": modle_key}
	if type(massage) == type(''):
		massage=json.loads(massage)
	data={"model": model_name,"messages":massage}
	# print(data)
	response = requests.post(modle_url, headers=headers, json=data)
	response_data = response.json()
	# print(response_data)
	choices = response_data.get("choices", [])
	# print(choices)
	if choices == None:
		rst_data= '当前模型不可用'
	else:
		rst_data = choices[0]["message"]["content"]
	return rst_data




modelscope_llm_modlelist=[
    'ZhipuAI/GLM-5',
    'moonshotai/Kimi-K2.5',
    'MiniMax/MiniMax-M2.5',
    'Qwen/Qwen3-Coder-480B-A35B-Instruct'
]

free_modle_list=[
	'glm-4-flash-250414',
	'glm-4-flash',
	'lite'
]


def select_inferencemoda(massage):
	period =get_beijing_time_period()
	if period == 1:
		for i in modelscope_llm_modlelist:
			rst_data = inferencemodel(massage,i,modelscope_url,modelscope_key)
			if '当前模型不可用' not in rst_data:
				rst_data=rst_data
				break
	else:
		for i in free_modle_list:
			if 'glm' in i:
				moda_url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
				moda_key=zp_key
				rst_data = free_llm_modle(massage,i,moda_url,moda_key)
			else:
				moda_url = 'https://spark-api-open.xf-yun.com/v1/chat/completions'
				moda_key=xinghuo_key
				rst_data = free_llm_modle(massage,i,moda_url,moda_key)
			if '当前模型不可用' not in rst_data:
				rst_data=rst_data
				break
	return rst_data

def select_free_inferencemoda(massage):
    moda_url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
    moda_key=zp_key
    headers = {"Content-Type": "application/json","Authorization": moda_key}
    data={"model": 'glm-4-flash',"messages":massage}
    rst_data = requests.post(moda_url, headers=headers, json=data)
    return rst_data

modelscope_llm_modlelist_v=[
    'Qwen/Qwen3-VL-8B-Instruct'
]

free_modle_list_v=[
	'glm-4.6v-flash',
	'glm-4v-flash'
]



def select_inferencemoda_v(massage):
	period =get_beijing_time_period()
	if period == 1:
		for i in modelscope_llm_modlelist_v:
			rst_data = inferencemodel(massage,i,modelscope_url,modelscope_key)
			if '当前模型不可用' not in rst_data:
				rst_data=rst_data
				break
	else:
		for i in free_modle_list_v:
			if 'glm' in i:
				moda_url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
				moda_key=zp_key
				rst_data = free_llm_modle(massage,i,moda_url,moda_key)
			if '当前模型不可用' not in rst_data:
				rst_data=rst_data
				break
	return rst_data




