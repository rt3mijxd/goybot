import React from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useGame } from '../context/GameContext'

export default function PotDisplay() {
  const { state } = useGame()
  const pot = state.pot || 0

  if (!pot) return null

  return (
    <div className="absolute left-1/2 top-[28%] -translate-x-1/2 z-10">
      <AnimatePresence mode="wait">
        <motion.div
          key={pot}
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.8, opacity: 0 }}
          className="bg-black/60 backdrop-blur-sm px-4 py-1.5 rounded-full border border-yellow-600/50"
        >
          <span className="text-yellow-400 font-bold text-sm">Банк: {pot}</span>
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
