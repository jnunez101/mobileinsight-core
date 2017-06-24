# Filename: android_mtk_log_monitor.py
"""
An MTK log parser

Author: Qianru Li, Zhehui Zhang
"""
import struct
import sys
import subprocess
import re
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

ANDROID_SHELL = "/system/bin/sh"

SMS_CP      = '\x90\x01\x00\x00' #400
MM_CM_REQ   = '\x91\x01\x00\x00' # 401
MM_AUTH_REQ = '\x92\x01\x00\x00' #402
GMM_UL      = '\x93\x01\x00\x00' #403
                    # (gmm_identity_response)/(gmm_rau_comp)/gmm_service_req
GMM_DL      = '\x94\x01\x00\x00' #404
                    # (gmm_rau_accept)/gmm_service_accept
SMS_RP      = '\x95\x01\x00\x00' #405
CC_UL       = '\x9e\x01\x00\x01' #414
CC_DL       = '\x9f\x01\x00\x00' #415
SM_PDP      = '\xa0\x01\x00\x00' #416
                    # (modify_pdp_accept/ul)
_2G_RR      = '\xf4\x01\x00\x00' #500
                    # (gprs_suspend_req_ul)/rr_ciphermode_command_dl/ul
_2G_RR_SI   = '\xf5\x01\x00\x00' #501
_2G_RR_MEAS = '\xf6\x01\x00\x00' #502
_2G_RR_CHNL = '\xf7\x01\x00\x00' #503

LTE_BCCH_BCH = '\xbc\x02\x00\x00'
LTE_BCCH_DL_SCH = '\xbd\x02\x00\x00'
LTE_DL_CCCH = '\xbe\x02\x00\x00'
LTE_DL_DCCH = '\xbf\x02\x00\x00'
LTE_PCCH = '\xc0\x02\x00\x00'
LTE_UL_CCCH = '\xc1\x02\x00\x00'
LTE_UL_DCCH = '\xc2\x02\x00\x00'
RRC_SI_MIB = '\xe8\x03\x00\x00'
RRC_SI_SB1 = '\xe9\x03\x00\x00'
RRC_SI_SB2 = '\xea\x03\x00\x00'
RRC_SI_SIB1 = '\xeb\x03\x00\x00'
RRC_SI_SIB2 = '\xec\x03\x00\x00'
RRC_SI_SIB3 = '\xed\x03\x00\x00'
RRC_SI_SIB4 = '\xee\x03\x00\x00'
RRC_SI_SIB5a = '\xef\x03\x00\x00'
RRC_SI_SIB5b = '\xf0\x03\x00\x00'
RRC_SI_SIB6 = '\xf1\x03\x00\x00'
RRC_SI_SIB7 = '\xf2\x03\x00\x00'
RRC_SI_SIB11 = '\xf6\x03\x00\x00'
RRC_SI_SIB11_BIS = '\xf7\x03\x00\x00'
RRC_SI_SIB12 = '\xf8\x03\x00\x00'
RRC_BCCH_RACH   = '\x85\x03\x00\x00'
RRC_DL_CCCH     = '\x86\x03\x00\x00'
RRC_DL_DCCH     = '\x87\x03\x00\x00'
RRC_PAGING_TYPE1 = '\x8b\x03\x00\x00'
RRC_CONN_REQ    = '\x8c\x03\x00\x00' #908
# RRC_UL_CCCH     = ['0xc0', '0x3', '0x0', '0x0']
RRC_UL_DCCH     = '\x8d\x03\x00\x00'
RRC_HANDOVERTOUTRANCOMMAND = '\x8f\x03\x00\x00'
RRC_INTERRATHANDOVERINFO = '\x90\x03\x00\x00'
EMM_SERVICE_REQUEST = '\x21\x03\x00\x00'
RRC_SI_SIB18 = '\x0e\x04\x00\x00'
RRC_SI_SIB19 = '\x0f\x04\x00\x00'
RRC_SI_SIB20 = '\x10\x04\x00\x00'

NAS_str     = "UMTS_NAS_OTA_Packet"
RRC_str     = "WCDMA_RRC_OTA_Packet"
LTE_RRC_str = "LTE_RRC_OTA_Packet"
LTE_NAS_str = "LTE_NAS_ESM_OTA_Incoming_Packet"



type_id_mapping = {
    # SMS_CP,
    MM_CM_REQ:[190,NAS_str,"NAS"],#"MM_CM_REQ"],
    MM_AUTH_REQ:[190,NAS_str,"NAS"],#"MM_AUTH_REQ"],
    GMM_UL:[190,NAS_str,"NAS"],#"GMM_UL"],
    GMM_DL:[190,NAS_str,"NAS"],#"GMM_DL"],
    # SMS_RP,
    CC_UL:[190,NAS_str,"NAS"],#"CC_UL"],
    CC_DL:[190,NAS_str,"NAS"],#"CC_DL"],
    SM_PDP:[190,NAS_str,"NAS"],#"SM_PDP"],
    # _2G_RR,
    # _2G_RR_SI,
    # _2G_RR_MEAS,
    # _2G_RR_CHNL,
    LTE_BCCH_BCH:[203,LTE_RRC_str,"LTE-RRC_BCCH_DL_SCH"],#"LTE_BCCH_BCH"],
    LTE_BCCH_DL_SCH:[203,LTE_RRC_str,"LTE-RRC_BCCH_DL_SCH"],#"LTE-RRC_BCCH_DL_SCH"],
    LTE_DL_CCCH:[204,LTE_RRC_str,"LTE-RRC_DL_CCCH"],#"LTE_DL_CCCH"],
    LTE_DL_DCCH:[201,LTE_RRC_str,"LTE-RRC_DL_DCCH"],#"LTE-RRC_DL_DCCH"],
    LTE_PCCH:[200,LTE_RRC_str,"LTE-RRC_PCCH"],#"LTE_PCCH"],
    LTE_UL_CCCH:[205,LTE_RRC_str,"LTE-RRC_UL_CCCH"],#"LTE_UL_CCCH"],
    LTE_UL_DCCH:[202,LTE_RRC_str,"LTE-RRC_UL_DCCH"],

    RRC_SI_MIB:[150,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_MIB"],
    RRC_SI_SB1:[181,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SB1"],
    RRC_SI_SB2:[182,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SB2"],
    RRC_SI_SIB1:[151,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB1"],
    RRC_SI_SIB2:[152,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB2"],
    RRC_SI_SIB3:[153,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB3"],
    RRC_SI_SIB4:[154,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB4"],
    RRC_SI_SIB5a:[155,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB5a"],
    RRC_SI_SIB5b:[155,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB5b"],
    RRC_SI_SIB6:[156,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB6"],
    RRC_SI_SIB7:[157,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB7"],
    RRC_SI_SIB11:[161,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB11"],
    RRC_SI_SIB12:[162,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB12"],
    RRC_SI_SIB18:[168,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB18"],
    RRC_SI_SIB19:[169,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB19"],
    RRC_SI_SIB20:[170,RRC_str,"RRC_COMPLETE_SIB"],#"RRC_SI_SIB20"],
    RRC_DL_CCCH:[102,RRC_str,"RRC_DL_CCCH"],
    RRC_DL_DCCH:[103,RRC_str,"RRC_DL_DCCH"],
    RRC_PAGING_TYPE1:[106,RRC_str,"RRC_DL_PCCH"],
    RRC_CONN_REQ:[100,RRC_str,"RRC_UL_CCCH"],
    # RRC_UL_CCCH,
    RRC_UL_DCCH:[101,RRC_str,"RRC_UL_DCCH"],
    RRC_HANDOVERTOUTRANCOMMAND:[103,RRC_str,"RRC_DL_DCCH"],#"RRC_HANDOVERTOUTRANCOMMAND"],
    RRC_INTERRATHANDOVERINFO:[103,RRC_str,"RRC_DL_DCCH"],#"RRC_INTERRATHANDOVERINFO"],
    EMM_SERVICE_REQUEST:[250,LTE_NAS_str,"LTE-NAS_EPS_PLAIN"]
}




# SMS_CP      = ['0x90', '0x1', '0x0', '0x0'] #400
# MM_CM_REQ   = ['0x91', '0x1', '0x0', '0x0'] # 401
# MM_AUTH_REQ = ['0x92', '0x1', '0x0', '0x0'] #402
# GMM_UL      = ['0x93', '0x1', '0x0', '0x0'] #403
#                     # (gmm_identity_response)/(gmm_rau_comp)/gmm_service_req
# GMM_DL      = ['0x94', '0x1', '0x0', '0x0'] #404
#                     # (gmm_rau_accept)/gmm_service_accept
# SMS_RP      = ['0x95', '0x1', '0x0', '0x0'] #405
# CC_UL       = ['0x9e', '0x1', '0x0', '0x0'] #414
# CC_DL       = ['0x9f', '0x1', '0x0', '0x0'] #415
# SM_PDP      = ['0xa0', '0x1', '0x0', '0x0'] #416
#                     # (modify_pdp_accept/ul)
# _2G_RR      = ['0xf4', '0x1', '0x0', '0x0'] #500
#                     # (gprs_suspend_req_ul)/rr_ciphermode_command_dl/ul
# _2G_RR_SI   = ['0xf5', '0x1', '0x0', '0x0'] #501
# _2G_RR_MEAS = ['0xf6', '0x1', '0x0', '0x0'] #502
# _2G_RR_CHNL = ['0xf7', '0x1', '0x0', '0x0'] #503

# LTE_BCCH_BCH = ['0xbc', '0x2', '0x0', '0x0']
# LTE_BCCH_DL_SCH = ['0xbd', '0x2', '0x0', '0x0']
# LTE_DL_CCCH = ['0xbe', '0x2', '0x0', '0x0']
# LTE_DL_DCCH = ['0xbf', '0x2', '0x0', '0x0']
# LTE_PCCH = ['0xc0', '0x2', '0x0', '0x0']
# LTE_UL_CCCH = ['0xc1', '0x2', '0x0', '0x0']
# LTE_UL_DCCH = ['0xc2', '0x2', '0x0', '0x0']
# RRC_SI_MIB = ['0xe8', '0x3', '0x0', '0x0']
# RRC_SI_SB1 = ['0xe9', '0x3', '0x0', '0x0']
# RRC_SI_SB2 = ['0xea', '0x3', '0x0', '0x0']
# RRC_SI_SIB1 = ['0xeb', '0x3', '0x0', '0x0']
# RRC_SI_SIB2 = ['0xec', '0x3', '0x0', '0x0']
# RRC_SI_SIB3 = ['0xed', '0x3', '0x0', '0x0']
# RRC_SI_SIB4 = ['0xee', '0x3', '0x0', '0x0']
# RRC_SI_SIB5a = ['0xef', '0x3', '0x0', '0x0']
# RRC_SI_SIB5b = ['0xf0', '0x3', '0x0', '0x0']
# RRC_SI_SIB6 = ['0xf1', '0x3', '0x0', '0x0']
# RRC_SI_SIB7 = ['0xf2', '0x3', '0x0', '0x0']
# RRC_SI_SIB11 = ['0xf6', '0x3', '0x0', '0x0']
# RRC_SI_SIB11_BIS = ['0xf7', '0x3', '0x0', '0x0']
# RRC_SI_SIB12 = ['0xf8', '0x3', '0x0', '0x0']
# RRC_BCCH_RACH   = ['0x85', '0x3', '0x0', '0x0']
# RRC_DL_CCCH     = ['0x86', '0x3', '0x0', '0x0']
# RRC_DL_DCCH     = ['0x87', '0x3', '0x0', '0x0']
# RRC_PAGING_TYPE1 = ['0x8b', '0x3', '0x0', '0x0']
# RRC_CONN_REQ    = ['0x8c', '0x3', '0x0', '0x0'] #908
# # RRC_UL_CCCH     = ['0xc0', '0x3', '0x0', '0x0']
# RRC_UL_DCCH     = ['0x8d', '0x3', '0x0', '0x0']
# RRC_HANDOVERTOUTRANCOMMAND = ['0x8f', '0x3', '0x0', '0x0']
# RRC_INTERRATHANDOVERINFO = ['0x90', '0x3', '0x0', '0x0']
# EMM_SERVICE_REQUEST = ['0x21', '0x3', '0x0', '0x0']
# RRC_SI_SIB18 = ['0xe', '0x4', '0x0', '0x0']
# RRC_SI_SIB19 = ['0xf', '0x4', '0x0', '0x0']
# RRC_SI_SIB20 = ['0x10', '0x4', '0x0', '0x0']

SMS_CP      = '\x90\x01\x00\x00' #400
MM_CM_REQ   = '\x91\x01\x00\x00' # 401
MM_AUTH_REQ = '\x92\x01\x00\x00' #402
GMM_UL      = '\x93\x01\x00\x00' #403
                    # (gmm_identity_response)/(gmm_rau_comp)/gmm_service_req
GMM_DL      = '\x94\x01\x00\x00' #404
                    # (gmm_rau_accept)/gmm_service_accept
SMS_RP      = '\x95\x01\x00\x00' #405
CC_UL       = '\x9e\x01\x00\x01' #414
CC_DL       = '\x9f\x01\x00\x00' #415
SM_PDP      = '\xa0\x01\x00\x00' #416
                    # (modify_pdp_accept/ul)
_2G_RR      = '\xf4\x01\x00\x00' #500
                    # (gprs_suspend_req_ul)/rr_ciphermode_command_dl/ul
_2G_RR_SI   = '\xf5\x01\x00\x00' #501
_2G_RR_MEAS = '\xf6\x01\x00\x00' #502
_2G_RR_CHNL = '\xf7\x01\x00\x00' #503

LTE_BCCH_BCH = '\xbc\x02\x00\x00'
LTE_BCCH_DL_SCH = '\xbd\x02\x00\x00'
LTE_DL_CCCH = '\xbe\x02\x00\x00'
LTE_DL_DCCH = '\xbf\x02\x00\x00'
LTE_PCCH = '\xc0\x02\x00\x00'
LTE_UL_CCCH = '\xc1\x02\x00\x00'
LTE_UL_DCCH = '\xc2\x02\x00\x00'
RRC_SI_MIB = '\xe8\x03\x00\x00'
RRC_SI_SB1 = '\xe9\x03\x00\x00'
RRC_SI_SB2 = '\xea\x03\x00\x00'
RRC_SI_SIB1 = '\xeb\x03\x00\x00'
RRC_SI_SIB2 = '\xec\x03\x00\x00'
RRC_SI_SIB3 = '\xed\x03\x00\x00'
RRC_SI_SIB4 = '\xee\x03\x00\x00'
RRC_SI_SIB5a = '\xef\x03\x00\x00'
RRC_SI_SIB5b = '\xf0\x03\x00\x00'
RRC_SI_SIB6 = '\xf1\x03\x00\x00'
RRC_SI_SIB7 = '\xf2\x03\x00\x00'
RRC_SI_SIB11 = '\xf6\x03\x00\x00'
RRC_SI_SIB11_BIS = '\xf7\x03\x00\x00'
RRC_SI_SIB12 = '\xf8\x03\x00\x00'
RRC_BCCH_RACH   = '\x85\x03\x00\x00'
RRC_DL_CCCH     = '\x86\x03\x00\x00'
RRC_DL_DCCH     = '\x87\x03\x00\x00'
RRC_PAGING_TYPE1 = '\x8b\x03\x00\x00'
RRC_CONN_REQ    = '\x8c\x03\x00\x00' #908
# RRC_UL_CCCH     = ['0xc0', '0x3', '0x0', '0x0']
RRC_UL_DCCH     = '\x8d\x03\x00\x00'
RRC_HANDOVERTOUTRANCOMMAND = '\x8f\x03\x00\x00'
RRC_INTERRATHANDOVERINFO = '\x90\x03\x00\x00'
EMM_SERVICE_REQUEST = '\x21\x03\x00\x00'
RRC_SI_SIB18 = '\x0e\x04\x00\x00'
RRC_SI_SIB19 = '\x0f\x04\x00\x00'
RRC_SI_SIB20 = '\x10\x04\x00\x00'


# mtk_log_parser_buff = []  # store bytes in current section
mtk_log_parser_buff = ''
first_header = False
msg_type = []
msg_enabled = []

def setfilter(m_type, m_enabled):
    global msg_type, msg_enabled
    msg_type = m_type
    msg_enabled = msg_enabled


def feed_binary(buff):
    global mtk_log_parser_buff
    msg_list = []
    cur_index = 0
    end_index = len(buff)
    print end_index
    # parse file into sections devided by '\0x8f\0x9a\0x9a\0x8d\0x04\0x00'
    header = '\xac\xca\x00\xff'
    header_magic = '\x8f\x9a\x9a\x8d\x04\x00'
    
    mtk_log_str = ''.join(map(lambda x: chr(struct.unpack('B',x)[0]), buff))
    mtk_log_str = re.sub('\xac\xca\x00\xff..','',mtk_log_str)
    new_log_len = len(mtk_log_str)
    # print len(mtk_log_str)

    loc = mtk_log_str.find('\x8f\x9a\x9a\x8d\x04\x00')
    while loc >= 0:
        # copy seek_pstrace_magic()
        pstrace = []

        msg_id = mtk_log_str[6+loc:10+loc]
        if msg_id in type_id_mapping:
            # calculate the length of raw_data
            decimal_high    = ord(mtk_log_str[10+loc])
            decimal_low     = ord(mtk_log_str[11+loc]) 
            length          = decimal_low * 256 + decimal_high

        if length > 0 and length < new_log_len - loc:
            raw_bytes = mtk_log_str[12+loc:12 + length+loc]
            raw_data = map(lambda x: x if (x != '\x00') else '\x00', raw_bytes)
            raw_msg = ['\x00'] * 3 + [msg_id] + ['\x00'] * 2 + [chr(decimal_low)] + [chr(decimal_high)] + raw_data
            pstrace.append(raw_msg)
            msg_list.append(pstrace)

        loc = mtk_log_str.find('\x8f\x9a\x9a\x8d\x04\x00',loc+12)

    return msg_list
    # print mtk_log_str.find('\x8f\x9a\x9a\x8d\x04\x00')

    # block by qianru
    # while cur_index != end_index:
    #     byte = buff[cur_index]
    #     # byte_value couldn't be print out
    #     byte_value = struct.unpack('B', byte)[0]
        
    #     mtk_log_parser_buff += chr(byte_value)
    #     # print chr(byte_value),
    #     if len(mtk_log_parser_buff) > 6:
    #         if mtk_log_parser_buff[-6:-2] == header:
    #             mtk_log_parser_buff = mtk_log_parser_buff[:-6]
    #             # print mtk_log_parser_buff
    #         if mtk_log_parser_buff[-6:] == header_magic:
    #             # print mtk_log_parser_buff
    #             print 'magic'
    #             res = seek_pstrace_magic(mtk_log_parser_buff)
    #             if res != []:
    #                 msg_list.append(res)
    #             mtk_log_parser_buff = ''
    #     cur_index += 1
    # return msg_list
    # block by qianru end


def decode(logger, raw_msg):
# def decode_tmp(raw_msg):
    """
    decode raw_msg and return the typeid, xml (for decoded message)

    sample input for ws_dissector:
    echo -ne
    '\x00\x00\x00\xc8\x00\x00\x00\x09\x40\x01\xBF\x28\x1A\xEB\xA0\x00\x00' |
    LD_LIBRARY_PATH="/data/data/edu.ucla.cs.wing.mobileinsight/files/data/"
    /data/data/edu.ucla.cs.wing.mobileinsight/files/data/android_pie_ws_dissector
    """
    msg_id = raw_msg[0][3]
    if msg_id not in type_id_mapping:
        return "",""
    type_str    = type_id_mapping[msg_id][1]
    raw_str     = type_id_mapping[msg_id][2]

    raw_msg[0][3] = chr(type_id_mapping[msg_id][0])
    # qianru-edit-end
    # print "global_msg_id ", type_str
    msg =  "\\" + "\\".join([format(ord(j), '#04x')[1:] for j in raw_msg[0]])
    output = msg

    # logger.log_info("lizhehan: Receive message: " + msg)
    # qianru-edit
    p = subprocess.Popen("su", executable=ANDROID_SHELL, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    output,err = p.communicate("echo -ne \'" + msg + "\' | LD_LIBRARY_PATH=" + logger.libs_path + ' ' + logger.ws_dissector_path + '\n')
    p.wait()
    end = output.rfind('>') + 1
    output = output[:end]
    # qianru-edit
    # logger.log_info("lizhehan: Output: " + output)
    return type_str, raw_str, output

def seek_pstrace_magic(bytes):
    global first_header
    pstrace = []

    if not first_header:
        first_header = True
        return pstrace

    msg_id = bytes[0:4]
    if msg_id in type_id_mapping:
        # calculate the length of raw_data
        decimal_high    = ord(bytes[4])
        decimal_low     = ord(bytes[5]) 
        length          = decimal_low * 256 + decimal_high
        
        if length > 0 and length < len(bytes):
            raw_bytes = bytes[6:6 + length]
            # raw_data = map(lambda x: x if (x != '0x0') else '0x00', raw_bytes)
            raw_data = map(lambda x: x if (x != '\x00') else '\x00', raw_bytes)
            
            raw_msg = ['\x00'] * 3 + [msg_id] + ['\x00'] * 2 + [bytes[5]] + [bytes[4]] + raw_data
            pstrace.append(raw_msg)
            # return pstrace
    return pstrace


def parse_mtk_log_magic(filename):
    msg_list = []
    # global a
    with open(filename, 'rb') as f:
        f.seek(0)
        byte = f.read(1)
        bytes_current = []  # store bytes in current section

        # parse file into sections devided by '\0x8f\0x9a\0x9a\0x8d\0x04\0x00'
        header = ['0xac', '0xca', '0x0', '0xff']
        header_magic = ['0x8f', '0x9a', '0x9a', '0x8d', '0x4', '0x0']
        while len(byte) == 1 and byte != 'ELF':
            # if a > 25:
            #     return msg_list
            # byte_value couldn't be print out
            byte_value = struct.unpack('B', byte)[0]
            bytes_current.append(hex(byte_value))
            if len(bytes_current) > 6:
                if bytes_current[-6:-2] == header:
                    bytes_current = bytes_current[:-6]
                if bytes_current[-6:] == header_magic:
                    res = seek_pstrace_magic(bytes_current)
                    if res != []:
                        msg_list.append(res)
                        # print 'yes'
                    bytes_current = []
            byte = f.read(1)
        res = seek_pstrace_magic(bytes_current)
        if res != []:
            msg_list.append(res)
            # print 'yes'
    return msg_list

# if __name__ == '__main__':
#     fp = open('./runtime.muxraw','r')
#     s = fp.read()
#     # print s 
#     # print '\x00\x00\x00\xc8\x00\x00\x00\x09\x40\x01\xBF\x28\x1A\xEB\xA0\x00\x00'
#     msgList = feed_binary(s)

#     for msg in msgList:
#         typeid, rawid, msgstr = decode_tmp(msg) #self for debug
