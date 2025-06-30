def recognize_stroke_style(smoothed_txt_path):
    """
    根據關鍵點資料判斷泳姿類型。
    此處使用簡化版本，請依實際需求改為模型分類。
    回傳泳姿字串：'freestyle'、'backstroke'、'breaststroke'、'butterfly'
    """
    # 範例邏輯：取中段關鍵點判斷平均手部位置
    import numpy as np

    with open(smoothed_txt_path, 'r') as f:
        lines = [line.strip().split() for line in f if line.strip()]

    mid_lines = lines[len(lines)//3: 2*len(lines)//3]
    left_hand_y = np.array([float(l[19]) for l in mid_lines])
    right_hand_y = np.array([float(l[22]) for l in mid_lines])
    shoulder_y = np.array([float(l[11]) for l in mid_lines])

    left_above = np.mean(left_hand_y < shoulder_y)
    right_above = np.mean(right_hand_y < shoulder_y)

    if left_above > 0.7 and right_above > 0.7:
        return 'backstroke'
    elif left_above < 0.3 and right_above < 0.3:
        return 'freestyle'
    elif np.std(left_hand_y) < 20 and np.std(right_hand_y) < 20:
        return 'breaststroke'
    else:
        return 'butterfly'