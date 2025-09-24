import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter1d

def plot_phase_on_col11_col17(data_dict, intersection_dict, waterline_y, output_txt = None):
    for key, values in data_dict.items():
        frames = np.array([v[0] for v in values])
        col10s = np.array([v[1] for v in values])
        col11s = np.array([v[2] for v in values])
        col16s = np.array([v[3] for v in values])
        col17s = np.array([v[4] for v in values])
        hip_xs = np.array([float(v[5]) for v in values])   # 人位移
        hip_start = hip_xs[0]
        distances = (hip_xs - hip_start) * (25 / 3840)
        
        col10s_smooth = uniform_filter1d(col10s, size=10)
        col16s_smooth = uniform_filter1d(col16s, size=10)

        direction = 'forward' if 'range1' in key else 'backward'
        intersection_frames = np.array(intersection_dict.get(key, []))

        # Recovery 區間
        recovery_mask = col17s < waterline_y
        recovery_regions = []
        in_region = False
        for i, flag in enumerate(recovery_mask):
            if flag and not in_region:
                start = frames[i]
                in_region = True
            elif not flag and in_region:
                end = frames[i - 1]
                in_region = False
                recovery_regions.append((start, end))
        if in_region:
            recovery_regions.append((start, frames[-1]))

        # Push 起點判斷
        push_starts = []
        for f in intersection_frames:
            f_idx = np.where(frames == f)[0]
            if len(f_idx) == 0 or f_idx[0] + 3 >= len(frames):
                continue
            idx = f_idx[0]
            window_col10 = col10s_smooth[idx+1:idx+4]
            window_col16 = col16s_smooth[idx+1:idx+4]
            if direction == 'forward' and np.all(window_col16 > window_col10):
                push_starts.append(int(f))
            elif direction == 'backward' and np.all(window_col16 < window_col10):
                push_starts.append(int(f))

        if len(intersection_frames) > 0:
            min_intersection_frame = min(intersection_frames)
            push_starts = [pf for pf in push_starts if pf >= min_intersection_frame]

        push_regions = []
        for pf in push_starts:
            next_recovery_starts = [r[0] for r in recovery_regions if r[0] > pf]
            push_end = next_recovery_starts[0] - 1 if next_recovery_starts else frames[-1]
            push_regions.append((pf, push_end))

        used_frames = set()
        for start, end in recovery_regions + push_regions:
            used_frames.update(range(start, end + 1))
        pull_regions = []
        in_pull = False
        for f in frames:
            if f not in used_frames:
                if not in_pull:
                    pull_start = f
                    in_pull = True
            else:
                if in_pull:
                    pull_end = f - 1
                    pull_regions.append((pull_start, pull_end))
                    in_pull = False
        if in_pull:
            pull_regions.append((pull_start, frames[-1]))

        if 'range1' in key and push_regions:
            first_push_start = push_regions[0][0]
            invalid_recovery = [r for r in recovery_regions if r[0] < first_push_start]
            invalid_push = [p for p in push_regions if p[0] < first_push_start]
            recovery_regions = [r for r in recovery_regions if r[0] >= first_push_start]
            push_regions = [p for p in push_regions if p[0] >= first_push_start]
            pull_regions += invalid_recovery + invalid_push

        updated_push_regions = push_regions.copy()
        updated_pull_regions = pull_regions.copy()
        for r_start, _ in recovery_regions:
            for p_start, p_end in updated_pull_regions:
                if p_end == r_start - 1:
                    updated_pull_regions.remove((p_start, p_end))
                    updated_push_regions.append((p_start, p_end))
                    break

        def merge_regions(region_list):
            region_list.sort(key=lambda x: x[0])
            merged = []
            for start, end in region_list:
                if not merged:
                    merged.append((start, end))
                else:
                    last_start, last_end = merged[-1]
                    if start <= last_end + 1:
                        merged[-1] = (last_start, max(last_end, end))
                    else:
                        merged.append((start, end))
            return merged
        push_regions = merge_regions(updated_push_regions)
        pull_regions = merge_regions(updated_pull_regions)
                
        # === 合併區間，確保邊界連續重疊 ===
        all_regions = [(s, e, "Pull") for s, e in pull_regions] + \
                    [(s, e, "Push") for s, e in push_regions] + \
                    [(s, e, "Recovery") for s, e in recovery_regions]

        # 依起點排序
        all_regions.sort(key=lambda x: x[0])

        # 連續化處理：end = 下一段 start
        pull_regions_new, push_regions_new, recovery_regions_new = [], [], []
        for i in range(len(all_regions)):
            s, e, t = all_regions[i]
            if i < len(all_regions) - 1:
                next_s = all_regions[i + 1][0]
                e = next_s  # 邊界重疊
            # 回填對應 list
            if t == "Pull":
                pull_regions_new.append((s, e))
            elif t == "Push":
                push_regions_new.append((s, e))
            else:
                recovery_regions_new.append((s, e))

        # 更新原本的區間
        pull_regions = pull_regions_new
        push_regions = push_regions_new
        recovery_regions = recovery_regions_new

        # === 組合輸出文字 ===
        output_text = f"\n{key} Phase Frames:\n"
        output_text += f"Pull regions: {pull_regions}\n"
        output_text += f"Push regions: {push_regions}\n"
        output_text += f"Recovery regions: {recovery_regions}\n"

        print(output_text)

        if output_txt is not None:
            with open(output_txt, "a", encoding="utf-8") as f:
                f.write(output_text)


                
        # def plot_phase(fig_title, y_values, y_label):
        #     fig, ax1 = plt.subplots(figsize=(15, 4))
        #     ax1.plot(frames, y_values, label=y_label, color='black')

        #     for start, end in recovery_regions:
        #         ax1.axvspan(start, end, color='green', alpha=0.2, label='Recovery')
        #     for start, end in push_regions:
        #         ax1.axvspan(start, end, color='orange', alpha=0.4, label='Push')
        #     for start, end in pull_regions:
        #         ax1.axvspan(start, end, color='blue', alpha=0.2, label='Pull')

        #     stage_starts = [r[0] for r in recovery_regions + push_regions + pull_regions]
        #     if frames[-1] not in stage_starts:
        #         stage_starts.append(frames[-1])
        #     stage_starts = sorted(set(stage_starts))
        #     frame_to_hip_x = dict(zip(frames, hip_xs))

        #     for i, f in enumerate(stage_starts):
        #         if f in frame_to_hip_x:
        #             delta_x = frame_to_hip_x[f] - hip_start
        #             disp_m = abs(delta_x * (25 / 3840))
        #             if i > 0:
        #                 prev_f = stage_starts[i - 1]
        #                 duration = (f - prev_f) / 30
        #             else:
        #                 duration = 0.0
        #             label_text = f"{disp_m:.2f}m, {duration:.2f}s"
        #             y_pos = np.interp(f, frames, y_values)
        #             ax1.annotate(label_text, xy=(f, y_pos), xytext=(0, -20),
        #                          textcoords="offset points", ha='center', fontsize=8,
        #                          bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.3))

        #     # 上方距離軸
        #     ax2 = ax1.twiny()
        #     ax2.set_xlim(ax1.get_xlim())
        #     tick_positions = []
        #     tick_labels = []

        #     for i in range(1, len(stage_starts)):
        #         start_f = stage_starts[i - 1]
        #         end_f = stage_starts[i]
        #         if start_f in frame_to_hip_x and end_f in frame_to_hip_x:
        #             delta_x = frame_to_hip_x[end_f] - frame_to_hip_x[start_f]
        #             segment_disp = abs(delta_x * (25 / 3840))
        #             label = f"{segment_disp:.2f}m"
        #             center_f = (start_f + end_f) // 2
        #             tick_positions.append(center_f)
        #             tick_labels.append(label)

        #     # 不要用 ax2.set_xticklabels 顯示，先清空
        #     ax2.set_xticks(tick_positions)
        #     ax2.set_xticklabels([''] * len(tick_positions))

        #     # 手動加上文字（Pull 對應的往上移）
        #     for i, center_f in enumerate(tick_positions):
        #         label = tick_labels[i]

        #         # 判斷屬於哪個區段（Pull 的話要往上）
        #         is_push = False
        #         for (ps, pe) in push_regions:
        #             if ps <= center_f <= pe:
        #                 is_push = True
        #                 break

        #         y_text = 1.05 if is_push else 1.01  # Pull 比其他的高
        #         ax2.text(center_f, y_text, label, fontsize=8, ha='center', va='bottom',
        #                 transform=ax2.get_xaxis_transform())

        #     ax2.set_xlabel("Segment Distance (m)", labelpad=20)
            
        #     ax1.set_xlabel('Frame')
        #     ax1.set_ylabel(y_label)
        #     ax1.set_title(f'{fig_title} - {key}', pad=30)
        #     ax1.grid(True)

        #     plt.tight_layout()
        #     plt.subplots_adjust(top=0.8)

        #     handles, labels = ax1.get_legend_handles_labels()
        #     by_label = dict(zip(labels, handles))
        #     ax1.legend(by_label.values(), by_label.keys(), fontsize=6)

        #     plt.show()

        # plot_phase('Shoulder Y (col11)', col11s, 'Shoulder Y')
        # plot_phase('Wrist Y (col17)', col17s, 'Wrist Y')
