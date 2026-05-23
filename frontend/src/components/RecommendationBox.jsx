import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useGame } from '../context/GameContext'

export default function RecommendationBox() {
  const { state } = useGame()
  const rec = state.recommendation
  const pos = state.recommendation_pos

  if (!rec) return null

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={rec}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: -10 }}
        className="bg-gradient-to-r from-purple-900/80 to-indigo-900/80 rounded-xl p-3 flex-1 min-w-[200px] border border-purple-500/30"
      >
        <div className="flex items-center gap-2 mb-1">
          <span className="text-purple-300 text-xs font-bold">GTO Рекомендация</span>
          {pos && <span className="text-xs text-purple-400">({pos})</span>}
        </div>
        <div className="text-white text-sm font-semibold whitespace-pre-line">{rec}</div>
      </motion.div>
    </AnimatePresence>
  )
}
