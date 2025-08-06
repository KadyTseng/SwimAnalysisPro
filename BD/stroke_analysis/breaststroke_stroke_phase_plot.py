import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import uniform_filter1d

def load_data_dict_from_txt(txt_path, range1, range2):
    def parse_line(line):
        parts = line.strip().split()
        if len(parts) > 20:
            try:
                frame = int(parts[0])
                col10 = float(parts[10])  # shoulder X
                col11 = float(parts[11])  # shoulder Y
                col13 = float(parts[13])  # elbow X
                col14 = float(parts[14])  # elbow Y
                col16 = float(parts[16])  # wrist X
                col17 = float(parts[17])  # wrist Y
                hip_x = float(parts[19])  # hip X
                return frame, col10, col11, col13, col14, col16, col17, hip_x
            except:
                return None
        return None

    data_dict = {'range1': [], 'range2': []}
    with open(txt_path, 'r') as f:
        for line in f:
            parsed = parse_line(line)
            if parsed:
                frame = parsed[0]
                if range1[0] <= frame <= range1[1]:
                    data_dict['range1'].append(parsed)
                elif range2[0] <= frame <= range2[1]:
                    data_dict['range2'].append(parsed)
    return data_dict

def plot_phase_on_col11_col17(data_dict, phase_frames_dict, waterline_y=None):
    for key, values in data_dict.items():
        frames = np.array([v[0] for v in values])
        col11s = np.array([v[2] for v in values])   # shoulder Y
        col14s = np.array([v[4] for v in values])   # elbow Y
        col17s = np.array([v[6] for v in values])   # wrist Y
        hip_xs = np.array([float(v[7]) for v in values])  # hip X
        hip_start = hip_xs[0]

        col11s_smooth = uniform_filter1d(col11s, size=10)
        col14s_smooth = uniform_filter1d(col14s, size=10)
        col17s_smooth = uniform_filter1d(col17s, size=10)

        propulsion_starts = phase_frames_dict[key]["propulsion_starts"]
        propulsion_ends = phase_frames_dict[key]["propulsion_ends"]
        recovery_ends = phase_frames_dict[key]["recovery_ends"]

        propulsion_regions = list(zip(propulsion_starts, propulsion_ends))
        recovery_regions = list(zip(propulsion_ends, recovery_ends))
        glide_regions = []
        for i in range(len(recovery_ends) - 1):
            glide_regions.append((recovery_ends[i], propulsion_starts[i + 1] - 1))
        if len(recovery_ends) > len(propulsion_starts) - 1:
            glide_regions.append((recovery_ends[-1], frames[-1]))

        if propulsion_starts:
            first_prop_start = propulsion_starts[0]
            if first_prop_start > frames[0]:
                glide_regions.insert(0, (frames[0], first_prop_start - 1))

        if recovery_ends and propulsion_starts:
            last_recovery_end = recovery_ends[-1]
            next_ps_candidates = [ps for ps in propulsion_starts if ps > last_recovery_end]
            if next_ps_candidates:
                next_ps = next_ps_candidates[0]
                if next_ps - last_recovery_end > 1:
                    glide_regions.append((last_recovery_end, next_ps - 1))

        def plot_phase(fig_title, y_values, y_label):
            fig, ax1 = plt.subplots(figsize=(15, 4))
            ax1.plot(frames, y_values, label=y_label, color='black')

            labeled = set()
            for start, end in propulsion_regions:
                if 'Propulsion' not in labeled:
                    ax1.axvspan(start, end, color='orange', alpha=0.4, label='Propulsion')
                    labeled.add('Propulsion')
                else:
                    ax1.axvspan(start, end, color='orange', alpha=0.4)

            for start, end in recovery_regions:
                if 'Recovery' not in labeled:
                    ax1.axvspan(start, end, color='green', alpha=0.2, label='Recovery')
                    labeled.add('Recovery')
                else:
                    ax1.axvspan(start, end, color='green', alpha=0.2)

            for start, end in glide_regions:
                if 'Glide' not in labeled:
                    ax1.axvspan(start, end, color='blue', alpha=0.2, label='Glide')
                    labeled.add('Glide')
                else:
                    ax1.axvspan(start, end, color='blue', alpha=0.2)

            stage_starts = sorted(set([s for s, _ in propulsion_regions + recovery_regions + glide_regions]))
            last_stage_end = max([e for _, e in propulsion_regions + recovery_regions + glide_regions])
            if last_stage_end not in stage_starts:
                stage_starts.append(last_stage_end)

            frame_to_hip_x = dict(zip(frames, hip_xs))

            for i, f in enumerate(stage_starts):
                if f in frame_to_hip_x:
                    delta_x = frame_to_hip_x[f] - hip_start
                    disp_m = abs(delta_x * (25 / 3840))
                    duration = (f - stage_starts[i - 1]) / 30 if i > 0 else 0.0
                    label_text = f"{disp_m:.2f}m, {duration:.2f}s"
                    y_val = np.interp(f, frames, y_values)
                    ax1.annotate(label_text, xy=(f, y_val), xytext=(0, -20),
                                textcoords="offset points", ha='center', fontsize=8,
                                bbox=dict(boxstyle="round,pad=0.2", fc="yellow", alpha=0.3))

            ax2 = ax1.twiny()
            ax2.set_xlim(ax1.get_xlim())
            tick_positions = []
            tick_labels = []

            for i in range(1, len(stage_starts)):
                start_f = stage_starts[i - 1]
                end_f = stage_starts[i]
                if start_f in frame_to_hip_x and end_f in frame_to_hip_x:
                    delta_x = frame_to_hip_x[end_f] - frame_to_hip_x[start_f]
                    segment_disp = abs(delta_x * (25 / 3840))
                    label = f"{segment_disp:.2f}m"
                    center_f = (start_f + end_f) // 2
                    tick_positions.append(center_f)
                    tick_labels.append(label)

            ax2.set_xticks(tick_positions)
            ax2.set_xticklabels([''] * len(tick_positions))

            for i, center_f in enumerate(tick_positions):
                label = tick_labels[i]
                is_propulsion = any(ps <= center_f <= pe for ps, pe in propulsion_regions)
                y_text = 1.06 if is_propulsion else 1.01
                ax2.text(center_f, y_text, label, fontsize=8, ha='center', va='bottom', transform=ax2.get_xaxis_transform())

            ax2.set_xlabel("Segment Distance (m)", labelpad=20)
            ax1.set_xlabel('Frame')
            ax1.set_ylabel(y_label)
            ax1.set_title(f'{fig_title} - {key}', pad=30)
            ax1.grid(True)
            plt.tight_layout()
            plt.subplots_adjust(top=0.8)

            handles, labels = ax1.get_legend_handles_labels()
            by_label = dict(zip(labels, handles))
            ax1.legend(by_label.values(), by_label.keys(), fontsize=6)
            plt.show()

        plot_phase('Shoulder Y - Breaststroke Phases', col11s_smooth, 'Shoulder Y')
        plot_phase('Wrist Y - Breaststroke Phases', col17s_smooth, 'Wrist Y')
