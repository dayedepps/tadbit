
// testing:
// gcc -shared tadbit_py.c -I/usr/include/python2.7 -lm -lpthread -std=gnu99 -fPIC -g -O3 -Wall -o tadbit_py.so

#include "Python.h"
#include "tadbit_alone.c"

/* The module doc string */
PyDoc_STRVAR(tadbitalone_py__doc__,
"here is a wrapper to tadbit function");

/* The function doc string */
PyDoc_STRVAR(_tadbitalone_wrapper__doc__,
"Run tadbit function in tadbitalone.c.\n\
    :argument obs: a python list of lists of floats, representing a list of linearized matrices.\n\
    :argument 0 n: number of rows or columns in the matrix\n\
    :argument 0 m: number of matrices\n\
    :argument 0 n_threads: number of threads to use\n\
    :argument 0 verbose: whether to display more/less information about process\n\
    :argument 0 max_tad_size: an integer defining maximum size of TAD. Default defines it to the number of rows/columns.\n\
    :argument 1 do_not_use_heuristic: whether to use or not some heuristics\n\
    :returns: a python list with each\n");


/* The wrapper to the underlying C function */
static PyObject *_tadbitalone_wrapper (PyObject *self, PyObject *args){
  PyObject **obs;
  int n;
  int m;
  int n_threads;
  const int verbose;
  const int max_tad_size;
  const int nbks;
  const int do_not_use_heuristic;
  /* output */
  tadbit_alone_output *seg = (tadbit_alone_output *) malloc(sizeof(tadbit_alone_output));

  if (!PyArg_ParseTuple(args, "Oiiiiiii:tadbitalone", &obs, &n, &m, &n_threads, &verbose, &max_tad_size, &nbks, &do_not_use_heuristic))
    return NULL;

  // convert list of lists to pointer o pointers
  // if something goes wrong, it is probably from there :S
  int i, j;
  int ** list;
  list = malloc(m * sizeof(int*));
  for (i = 0 ; i < m ; i++ )
    list[i] = malloc(n*n * sizeof(int));
  for (i = 0 ; i < m ; i++)
    for (j = 0 ; j < n*n ; j++)
      list[i][j] = PyInt_AS_LONG(PyTuple_GET_ITEM(PyList_GET_ITEM(obs, i), j));

  // run tadbit
  tadbit_alone(list, n, m, n_threads, verbose, max_tad_size, nbks, do_not_use_heuristic, seg);

  // store each tadbit output
  int       mbreaks     = seg->maxbreaks;
  int       nbreaks_opt = seg->nbreaks_opt;
  int    *  passages    = seg->passages;
  double *  llikmat     = seg->llikmat;
  double ** weights     = seg->weights;
  double *  mllik       = seg->mllik;
  int    *  bkpts       = seg->bkpts;

  // declare python objects to store lists
  PyObject * py_bkpts;
  PyObject * py_llikmat;
  PyObject * py_mllik;
  PyObject * py_result;
  PyObject * py_passages;
  PyObject * py_weights;
  PyObject * temp;

  // get bkpts
  /* int dim = nbreaks_opt*n; */
  const int MAXBREAKS = nbks ? nbks : n/5;
  int dim = MAXBREAKS * n;
  py_bkpts = PyList_New(dim);
  for(i = 0 ; i < dim; i++)
    PyList_SetItem(py_bkpts, i, PyInt_FromLong(bkpts[i]));

  /* This is to return directly the list of breaks found
  j = 0;
  py_bkpts = PyList_New(nbreaks_opt);
  for(i = 0 ; i < n; i++){
    if (bkpts[i+dim]==1){
      PyList_SetItem(py_bkpts, j, PyInt_FromLong(i));
      j++;
    }
  }
  */

  // get passages
  py_passages = PyList_New(n);
  for(i = 0 ; i < n; i++)
    PyList_SetItem(py_passages, i, PyFloat_FromDouble(passages[i]));

  // get llikmat
  py_llikmat = PyList_New(n*n);
  for(i = 0 ; i < n*n; i++)
    PyList_SetItem(py_llikmat, i, PyFloat_FromDouble(llikmat[i]));

  // get weights
  py_weights = PyList_New(m);
  for(i = 0 ; i < m; i++){
    temp = PyList_New(n*n);
    PyList_SetItem(py_weights, i, temp);
    for(j = 0 ; j < n*n; j++){
      PyList_SetItem(temp, j, PyFloat_FromDouble(weights[i][j]));
    }
  }

  // get mllik
  py_mllik = PyList_New(mbreaks);
  for(i = 0 ; i < mbreaks ; i++)
    PyList_SetItem(py_mllik, i, PyFloat_FromDouble(mllik[i]));

  // group results into a python list
  py_result = PyList_New(7);

  PyList_SetItem(py_result, 0, PyInt_FromLong(mbreaks));
  PyList_SetItem(py_result, 1, PyInt_FromLong(nbreaks_opt));
  PyList_SetItem(py_result, 2, py_passages);
  PyList_SetItem(py_result, 3, py_llikmat);
  PyList_SetItem(py_result, 4, py_mllik);
  PyList_SetItem(py_result, 5, py_bkpts);
  PyList_SetItem(py_result, 6, py_weights);

  // free many things... no leaks here!!
  // TODO: use 'destroy_tadbit_output'
  free(seg);
  free(passages);
  free(llikmat);
  int k;
  for (k = 0 ; k < m ; k++){
    //free(obs[k]);
    free(weights[k]);
    free(list[k]);
  }
  //free(obs);
  free(weights);
  free(list);
  free(mllik);
  free(bkpts);
  //free(py_bkpts);
  //free(py_llikmat);
  //free(py_mllik);
  //free(py_result);
  //free(py_passages);
  //free(py_weights);

  return py_result;
}

/* A list of all the methods defined by this module. */
/* The {NULL, NULL} entry indicates the end of the method definitions */
static PyMethodDef tadbitalone_py_methods[] = {
	{"_tadbitalone_wrapper",  _tadbitalone_wrapper, METH_VARARGS, _tadbitalone_wrapper__doc__},
	{NULL, NULL}      /* sentinel */
};

/* When Python imports a C module named 'X' it loads the module */
/* then looks for a method named "init"+X and calls it.  Hence */
/* for the module "mandelbrot" the initialization function is */
/* across operating systems and between C and C++ compilers */
PyMODINIT_FUNC
inittadbitalone_py(void)
{
	/* There have been several InitModule functions over time */
	Py_InitModule3("tadbitalone_py", tadbitalone_py_methods,
                   tadbitalone_py__doc__);
}
