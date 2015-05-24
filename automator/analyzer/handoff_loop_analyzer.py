#! /usr/bin/env python
"""
handoff_loop_analyzer.py

An analyzer for handoff loop detection and resolution

Author: Yuanjie Li
"""
import xml.etree.ElementTree as ET
from analyzer import *
from rrc_analyzer import RrcAnalyzer

class HandoffLoopAnalyzer(Analyzer):

	def __init__(self):

		Analyzer.__init__(self)

		#include analyzers
		#V1: RrcAnalyzer only
		#V2: RrcAnalyzer + UeAnanlyzer

		self.__rrc_analyzer = RrcAnalyzer()

		self.include_analyzer(self.__rrc_analyzer,[self.__loop_detection])

	def __loop_detection(self,msg):
		"""
			Detection persistent loops, configure device to avoid it
		"""
		if msg.type_id!="RrcAnalyzer":
			return

		"""
			Implementation plan:
			step 1: inter-freq/RAT only in idle-state
			step 2: introduce intra-freq in idle-state
			step 3: introduce cell-individual offsets
			step 4: introduce active-state handoff
		"""

		#Get cell list and configurations
		cell_list = self.__rrc_analyzer.get_cell_list()
		cell_config = {}	# each cell's configuration

		cell_visited = {x:False for x in cell_list} # mark if a cell has been visited
		cell_neighbor_visited = {} #boolean matrix: [i][j] indicates if ci->cj has been visited

		#test
		print cell_list
		for cell in cell_list:
			self.__rrc_analyzer.get_cell_config(cell).dump()

		#Setup neighboring cell matrix
		for cell in cell_list:

			cell_config[cell]=self.__rrc_analyzer.get_cell_config(cell)
			cell_freq=cell_config[cell].status.freq
			inter_freq_dict=cell_config[cell].sib.inter_freq_config
			neighbor_cells=[] 

			# #test
			# cell_config[cell].dump()
			
			#add intra-freq neighbors
			neighbor_cells+=self.__rrc_analyzer.get_cell_on_freq(cell_freq)
			neighbor_cells.remove(cell)	#remove the current cell itself

			#add inter-freq/RAT neighbors	
			for freq in inter_freq_dict:
				neighbor_cells+=self.__rrc_analyzer.get_cell_on_freq(freq)
			
			#initially all links are marked unvisited
			cell_neighbor_visited[cell]={x:False for x in neighbor_cells}

		if cell_list:

			# We implement the loop detection algorithm in Proposition 3,
			# because preferences are observed to be inconsistent

			while False in cell_visited.itervalues():	# some cells have not been explored yet	

				# In each round, we report loops with *unvisited_cell* involved			
				unvisited_cell=None
				#find an unvisited cell
				for cell in cell_list:
					if not cell_visited[cell]:
						unvisited_cell=cell
						cell_visited[cell]=True
						break

				dfs_stack=[unvisited_cell]		
				# For ci->ci+1, a ci's rss lower bound that satisifes this handoff
				# virtual (normalized) measurements are used
				virtual_rss=[0]
				# For dfs_stack[0]->dfs_stack[1], indicates whether ci's rss matters	
				dont_care=False

				while dfs_stack:
					src_cell = dfs_stack.pop()
					src_rss = virtual_rss.pop()
					dst_cell = None
					dst_rss = None

					#Find a next cell to handoff
					for cell in cell_neighbor_visited[src_cell]:
						#eliminate duplicate: visited cells are not visited
						if not cell_neighbor_visited[src_cell][cell]\
						and not cell_visited[cell]\
						and (not dfs_stack or cell not in dfs_stack[1:]):	
							dst_cell = cell
							cell_neighbor_visited[src_cell][dst_cell]=True
							break

					if dst_cell==None:
						#src_cell's all neighbors have been visited
						continue

					src_freq=cell_config[src_cell].status.freq
					dst_freq=cell_config[dst_cell].status.freq
					dst_config=cell_config[src_cell].get_cell_reselection_config(dst_cell,dst_freq)

					src_pref=cell_config[src_cell].sib.serv_config.priority
					dst_pref=dst_config.freq

					# a potential loop with dst_cell
					if dst_cell in dfs_stack: 
						# dst_cell==dfs_stack[0]
						# dfs_stack and dont_care must not be empty!!!

						loop_happen = False
						if dont_care:
							#loop if src_cell->dst_cell happens under src_rss only
							#intra-freq: loop must happens
							intra_freq_loop = (src_freq==dst_freq)
							#inter-freq/RAT: loop happens in equal/high-pref reselection
							inter_freq_loop1 = (src_freq!=dst_freq and src_pref<=dst_freq)
							#inter-freq/RAT: low-pref reselection happens
							inter_freq_loop2 = (src_freq!=dst_freq and src_pref>dst_freq \
							and src_rss<cell_config[src_cell].sib.serv_config.threshserv_low)

							loop_happen = intra_freq_loop or inter_freq_loop1 \
								or inter_freq_loop2
						else:
							#loop if src_cell->dst_cell happens under src_rss and dst_rss
							dst_rss = virtual_rss[0]

							intra_freq_loop = (src_freq==dst_freq \
								and dst_rss>=src_rss+dst_config.offset)

							inter_freq_loop1 = (src_freq!=dst_freq and src_pref==dst_freq \
								and dst_rss>=src_rss+dst_config.offset) 

							inter_freq_loop2 = (src_freq!=dst_freq and src_pref<dst_freq \
								and dst_rss>=dst_config.threshx_high)

							inter_freq_loop3 = (src_freq!=dst_freq and src_pref>dst_freq \
								and src_rss<cell_config[src_cell].sib.serv_config.threshserv_low \
								and dst_rss>=dst_config.threshx_low)

							loop_happen = intra_freq_loop or inter_freq_loop1 \
								or inter_freq_loop2 or inter_freq_loop3

						if loop_happen:
							#report loop
							loop_report="Persistent loop: "
							for cell in dfs_stack:
								loop_report=loop_report+str(cell)+"->"
							loop_report=loop_report+str(src_cell)+"->"+str(dst_cell)
							print loop_report
							
						dfs_stack.append(src_cell)
						virtual_rss.append(src_rss)
						continue

					else:
						if src_freq==dst_freq:	#intra-freq reselection
							if not dfs_stack:
								dont_care = False
							dst_rss=src_rss+dst_config.offset
							dfs_stack.append(src_cell)
							dfs_stack.append(dst_cell)
							virtual_rss.append(src_rss)
							virtual_rss.append(dst_rss)
						else:
							if src_pref<dst_pref:
								if not dfs_stack:
									dont_care = True
								dfs_stack.append(src_cell)
								dfs_stack.append(dst_cell)
								virtual_rss.append(src_rss)
								virtual_rss.append(dst_config.threshx_high)
							elif src_pref>dst_pref:
								threshserv=cell_config[src_cell].sib.serv_config.threshserv_low
								if src_rss >= threshserv:	#no loop, pass the dst_cell
									dfs_stack.append(src_cell)
									virtual_rss.append(src_rss)
								else:
									if not dfs_stack:
										dont_care = False
									dfs_stack.append(src_cell)
									dfs_stack.append(dst_cell)
									virtual_rss.append(src_rss)
									virtual_rss.append(dst_config.threshx_low)
							else:	
								if not dfs_stack:
									dont_care = False
								dst_rss=src_rss+dst_config.offset
								dfs_stack.append(src_cell)
								dfs_stack.append(dst_cell)
								virtual_rss.append(src_rss)
								virtual_rss.append(dst_rss)

