import React from 'react'
import { motion } from 'framer-motion'

const SUIT_SYMBOLS = { s: '♠', h: '♥', d: '♦', c: '♣' }
const SUIT_COLORS = { s: '#1a1a2e', h: '#e63946', d: '#4361ee', c: '#2d6a4f' }

export default function Card({ card, size = 'md', faceDown = false }) {
  if (!card || card === '??') faceDown = true

  const sizes = {
    xs: { w: 26, h: 38, text: 'text-[9px]', suit: 'text-[10px]' },
    sm: { w: 36, h: 52, text: 'text-xs', suit: 'text-sm' },
    md: { w: 48, h: 68, text: 'text-sm', suit: 'text-lg' },
    lg: { w: 64, h: 90, text: 'text-base', suit: 'text-xl' },
  }
  const s = sizes[size] || sizes.md

  if (faceDown) {
    return (
      <motion.div
        initial={{ rotateY: 180 }}
        animate={{ rotateY: 0 }}
        transition={{ duration: 0.3 }}
        className="rounded-lg shadow-lg flex items-center justify-center"
        style={{
          width: s.w, height: s.h,
          background: 'linear-gradient(135deg, #1e3a5f 0%, #0d1b2a 100%)',
          border: '2px solid #2a4a6b',
        }}
      >
        <div className="text-blue-400 opacity-50 text-lg">?</div>
      </motion.div>
    )
  }

  const rank = card.slice(0, -1)
  const suit = card.slice(-1).toLowerCase()
  const suitSymbol = SUIT_SYMBOLS[suit] || suit
  const color = SUIT_COLORS[suit] || '#333'
  const isRed = suit === 'h' || suit === 'd'

  return (
    <motion.div
      initial={{ rotateY: -90, scale: 0.8 }}
      animate={{ rotateY: 0, scale: 1 }}
      transition={{ duration: 0.3 }}
      className="rounded-lg shadow-lg flex flex-col items-center justify-center bg-white relative"
      style={{ width: s.w, height: s.h, border: '1px solid #ccc' }}
    >
      <span className={`font-bold ${s.text} ${isRed ? 'text-red-600' : 'text-gray-900'}`}>
        {rank}
      </span>
      <span className={`${s.suit} ${isRed ? 'text-red-600' : 'text-gray-900'}`}>
        {suitSymbol}
      </span>
    </motion.div>
  )
}
