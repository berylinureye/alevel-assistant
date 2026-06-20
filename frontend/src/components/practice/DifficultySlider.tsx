interface Props {
  min: number
  max: number
  onMinChange: (v: number) => void
  onMaxChange: (v: number) => void
}

const LABELS = ['', '简单', '中等', '标准', '较难', '挑战']

export function DifficultySlider({ min, max, onMinChange, onMaxChange }: Props) {
  return (
    <div>
      <label className="mb-2 block text-sm font-medium text-gray-700">
        难度范围: {LABELS[min]} ~ {LABELS[max]}
      </label>
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <label className="text-xs text-gray-500">最低</label>
          <input
            type="range"
            min={1}
            max={5}
            value={min}
            onChange={(e) => {
              const v = Number(e.target.value)
              onMinChange(v)
              if (v > max) onMaxChange(v)
            }}
            className="w-full accent-blue-500"
          />
        </div>
        <div className="flex-1">
          <label className="text-xs text-gray-500">最高</label>
          <input
            type="range"
            min={1}
            max={5}
            value={max}
            onChange={(e) => {
              const v = Number(e.target.value)
              onMaxChange(v)
              if (v < min) onMinChange(v)
            }}
            className="w-full accent-blue-500"
          />
        </div>
      </div>
      <div className="mt-1 flex justify-between text-xs text-gray-400">
        {LABELS.slice(1).map((_, i) => (
          <span key={i}>{i + 1}</span>
        ))}
      </div>
    </div>
  )
}
