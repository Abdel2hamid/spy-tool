'use client';

import { Search, TrendingUp, BarChart3 } from 'lucide-react';
import { KeywordOpportunity } from '@/lib/api';

interface KeywordOpportunityCardProps {
  keyword: KeywordOpportunity;
}

export function KeywordOpportunityCard({ keyword }: KeywordOpportunityCardProps) {
  const getDifficultyColor = (difficulty: number) => {
    if (difficulty < 33) return 'text-green-600 bg-green-50';
    if (difficulty < 66) return 'text-yellow-600 bg-yellow-50';
    return 'text-red-600 bg-red-50';
  };

  const getDifficultyLabel = (difficulty: number) => {
    if (difficulty < 33) return 'Easy';
    if (difficulty < 66) return 'Medium';
    return 'Hard';
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-primary-50 rounded-lg">
            <Search className="w-4 h-4 text-primary-600" />
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">{keyword.keyword}</h3>
            <p className="text-sm text-gray-500">
              {keyword.search_volume.toLocaleString()} monthly searches
            </p>
          </div>
        </div>
        
        <div className={`px-2 py-1 rounded-full text-xs font-medium ${getDifficultyColor(keyword.difficulty)}`}>
          {getDifficultyLabel(keyword.difficulty)}
        </div>
      </div>
      
      <div className="mt-4 grid grid-cols-3 gap-4">
        <div>
          <p className="text-xs text-gray-500">Difficulty</p>
          <p className="font-semibold text-gray-900">{keyword.difficulty.toFixed(0)}%</p>
        </div>
        <div>
          <p className="text-xs text-gray-500">Trend</p>
          <div className="flex items-center gap-1">
            <TrendingUp className={`w-3 h-3 ${keyword.trend > 0 ? 'text-green-500' : 'text-red-500'}`} />
            <p className="font-semibold text-gray-900">{keyword.trend.toFixed(0)}%</p>
          </div>
        </div>
        <div>
          <p className="text-xs text-gray-500">Score</p>
          <p className="font-semibold text-primary-600">{keyword.opportunity_score.toFixed(1)}</p>
        </div>
      </div>
    </div>
  );
}
