from ghidra.app.decompiler import DecompileOptions
from ghidra.app.decompiler import DecompInterface
from ghidra.util.task import ConsoleTaskMonitor

def getString(addr):
	mem = currentProgram.getMemory()
	core_name_str = ""
	while True:
		byte = mem.getByte(addr.add(len(core_name_str)))
		if byte == 0:
			return core_name_str
		core_name_str += chr(byte)

def LabelFunctions(labelingFunction):
	# Get decompiler interface
	options = DecompileOptions()
	monitor = ConsoleTaskMonitor()
	ifc = DecompInterface()
	ifc.setOptions(options)
	ifc.openProgram(currentProgram)

	# Get reference to `labelingFunction`
	fm = currentProgram.getFunctionManager()
	rm = currentProgram.getReferenceManager()

	funcs = fm.getFunctions(True)
	register_function = None
	for func in funcs:
		if func.getName() == labelingFunction:
			register_function = func
			break

	if register_function == None:
		print("{0} not found.".format(labelingFunction))
		return

	# Get xrefs to "labelingFunction"
	entry_point = register_function.getEntryPoint()
	# xrefs = getReferencesTo(entry_point)
	xrefs = rm.getReferencesTo(entry_point)
	callers = []
	for xref in xrefs:
		from_addr = xref.getFromAddress()
		caller = fm.getFunctionContaining(from_addr)
		if caller not in callers:
			callers.append(caller)

	# Process callers (functions calling `labelingFunction`)
	for caller in callers:
		if not caller:
			continue
		# Skip functions that have already been named
		if caller.getName().find("FUN_") == -1:
			continue
		print(caller.getName())
		res = ifc.decompileFunction(caller, 60, monitor)
		hf = res.getHighFunction()
		opiter = hf.getPcodeOps()
		while opiter.hasNext():
			op = opiter.next()
			mnemonic = op.getMnemonic()
			if mnemonic == "CALL":
				call_target = op.getInput(0)
				if call_target.getAddress() == entry_point:
					# Get the game name from path
					exe_name = op.getInput(2)
					exe_name_def = exe_name.getDef()
					exe_name_addr = toAddr(exe_name_def.getInput(0).getOffset())
					exe_string = getString(exe_name_addr)
					# Some functions contain a second call to this function
					# these use paths that dont begin with C:/dev/EXE so ignore those
					if exe_string.find("C:/dev/EXE/") == -1:
						continue
					print(exe_string)
					# Get the game name from the path
					exe_string2 = exe_string.split("/")[3]
					# get the function name
					func_name = op.getInput(3)
					func_name_def = func_name.getDef()
					func_name_addr = -1
					# Sometimes ghidra doesnt define the address as a string
					# this takes those into account
					if func_name_def.getMnemonic() == "PTRSUB":
						print(func_name_def.getInput(1).getOffset())
						func_name_addr = toAddr(func_name_def.getInput(1).getOffset())
					else:
						func_name_addr = toAddr(func_name_def.getInput(0).getOffset())
					func_string = getString(func_name_addr)
					# Combine the game name and function name
					new_func_name = "{0}{1}".format(exe_string2, func_string)
					print(exe_string2)
					print(func_string)
					print(new_func_name)
					# Set new name to calling function
					caller.setName(new_func_name, ghidra.program.model.symbol.SourceType.DEFAULT)
# EXE1
LabelFunctions("FUN_71000565dc")
# EXE2 and EXE3
LabelFunctions("FUN_71000565e4")

# EXE4 EXE5 EXE6
LabelFunctions("FUN_71000447c4")